#!/usr/bin/env python

# Copyright 2017 Johns Hopkins University (Shinji Watanabe)
#  Apache 2.0  (http://www.apache.org/licenses/LICENSE-2.0)

import copy
import logging
import os

import numpy as np

# chainer related
import chainer
from chainer import training
from chainer.training import extension

# io related
import kaldi_io_py

# matplotlib related
import matplotlib
matplotlib.use('Agg')


# * -------------------- training iterator related -------------------- *
def make_batchset(data, batch_size, max_length_in, max_length_out, num_batches=0):
    # sort it by input lengths (long to short)
    sorted_data = sorted(data.items(), key=lambda data: int(
        data[1]['input'][0]['shape'][0]), reverse=True)
    logging.info('# utts: ' + str(len(sorted_data)))
    # change batchsize depending on the input and output length
    minibatch = []
    start = 0
    while True:
        ilen = int(sorted_data[start][1]['input'][0]['shape'][0])
        olen = int(sorted_data[start][1]['output'][0]['shape'][0])
        factor = max(int(ilen / max_length_in), int(olen / max_length_out))
        # if ilen = 1000 and max_length_in = 800
        # then b = batchsize / 2
        # and max(1, .) avoids batchsize = 0
        b = max(1, int(batch_size / (1 + factor)))
        end = min(len(sorted_data), start + b)
        minibatch.append(sorted_data[start:end])
        if end == len(sorted_data):
            break
        start = end
    if num_batches > 0:
        minibatch = minibatch[:num_batches]
    logging.info('# minibatches: ' + str(len(minibatch)))

    return minibatch


def load_inputs_and_targets(batch, use_speaker_embedding=False):
    """Function to load inputs and targets from list of dicts

    :param list batch: list of dict which is subset of loaded data.json
    :param bool use_speaker_embedding: whether to load speaker embedding vector
    :return: list of input feature sequences [(T_1, D), (T_2, D), ..., (T_B, D)]
    :rtype: list of float ndarray
    :return: list of target token id sequences [(T_1), (T_2), ..., (T_B)]
    :rtype: list of int ndarray
    :return: list of speaker embedding vectors (only if use_speaker_embedding = True)
    :rtype: list of float adarray
    """
    # check input format
    assert isinstance(batch[0], dict)

    # load acoustic features and target sequence of token ids
    xs = [kaldi_io_py.read_mat(b[1]['input'][0]['feat']) for b in batch]
    ys = [b[1]['output'][0]['tokenid'].split() for b in batch]

    # get index of non-zero length samples
    nonzero_idx = filter(lambda i: len(ys[i]) > 0, range(len(xs)))
    nonzero_sorted_idx = sorted(nonzero_idx, key=lambda i: -len(xs[i]))
    if len(nonzero_sorted_idx) != len(xs):
        logging.warning('Target sequences include empty tokenid (batch %d -> %d).' % (
            len(xs), len(nonzero_sorted_idx)))

    # remove zero-length samples
    xs = [xs[i] for i in nonzero_sorted_idx]
    ys = [np.fromiter(map(int, ys[i]), dtype=np.int64) for i in nonzero_sorted_idx]

    # load speaker embedding
    if use_speaker_embedding:
        spembs = [kaldi_io_py.read_vec_flt(b[1]['input'][1]['feat']) for b in batch]
        spembs = [spembs[i] for i in nonzero_sorted_idx]
        return xs, ys, spembs
    else:
        return xs, ys


def pad_ndarray_list(batch, pad_value):
    """FUNCTION TO PERFORM PADDING OF NDARRAY LIST

    :param list batch: list of the ndarray [(T_1, D), (T_2, D), ..., (T_B, D)]
    :param float pad_value: value to pad
    :return: padded batch with the shape (B, Tmax, D)
    :rtype: ndarray
    """
    bs = len(batch)
    maxlen = max([b.shape[0] for b in batch])
    if len(batch[0].shape) >= 2:
        batch_pad = np.zeros((bs, maxlen) + batch[0].shape[1:])
    else:
        batch_pad = np.zeros((bs, maxlen))
    batch_pad.fill(pad_value)
    for i, b in enumerate(batch):
        batch_pad[i, :b.shape[0]] = b

    del batch

    return batch_pad


# * -------------------- chainer extension related -------------------- *
class CompareValueTrigger(object):
    '''Trigger invoked when key value getting bigger or lower than before

    Args:
        key (str): Key of value.
        compare_fn: Function to compare the values.
        trigger: Trigger that decide the comparison interval

    '''

    def __init__(self, key, compare_fn, trigger=(1, 'epoch')):
        self._key = key
        self._best_value = None
        self._interval_trigger = training.util.get_trigger(trigger)
        self._init_summary()
        self._compare_fn = compare_fn

    def __call__(self, trainer):
        observation = trainer.observation
        summary = self._summary
        key = self._key
        if key in observation:
            summary.add({key: observation[key]})

        if not self._interval_trigger(trainer):
            return False

        stats = summary.compute_mean()
        value = float(stats[key])  # copy to CPU
        self._init_summary()

        if self._best_value is None:
            # initialize best value
            self._best_value = value
            return False
        elif self._compare_fn(self._best_value, value):
            return True
        else:
            self._best_value = value
            return False

    def _init_summary(self):
        self._summary = chainer.reporter.DictSummary()


def restore_snapshot(model, snapshot, load_fn=chainer.serializers.load_npz):
    '''Extension to restore snapshot'''
    @training.make_extension(trigger=(1, 'epoch'))
    def restore_snapshot(trainer):
        _restore_snapshot(model, snapshot, load_fn)

    return restore_snapshot


def _restore_snapshot(model, snapshot, load_fn=chainer.serializers.load_npz):
    load_fn(snapshot, model)
    logging.info('restored from ' + str(snapshot))


def adadelta_eps_decay(eps_decay):
    '''Extension to perform adadelta eps decay'''
    @training.make_extension(trigger=(1, 'epoch'))
    def adadelta_eps_decay(trainer):
        _adadelta_eps_decay(trainer, eps_decay)

    return adadelta_eps_decay


def _adadelta_eps_decay(trainer, eps_decay):
    optimizer = trainer.updater.get_optimizer('main')
    # for chainer
    if hasattr(optimizer, 'eps'):
        current_eps = optimizer.eps
        setattr(optimizer, 'eps', current_eps * eps_decay)
        logging.info('adadelta eps decayed to ' + str(optimizer.eps))
    # pytorch
    else:
        for p in optimizer.param_groups:
            p["eps"] *= eps_decay
            logging.info('adadelta eps decayed to ' + str(p["eps"]))


class PlotAttentionReport(extension.Extension):
    """Plot attention reporter

    :param function att_vis_fn: function of attention visualization
    :param list data: list json utt key items
    :param str outdir: directory to save figures
    :param function converter: function to convert data
    :param bool reverse: If True, input and output length are reversed
    """

    def __init__(self, att_vis_fn, data, outdir, converter, reverse=False):
        self.att_vis_fn = att_vis_fn
        self.data = copy.deepcopy(data)
        self.outdir = outdir
        self.converter = converter
        self.reverse = reverse
        if not os.path.exists(self.outdir):
            os.makedirs(self.outdir)

    def __call__(self, trainer):
        batch = self.converter([self.data])
        att_ws = self.att_vis_fn(*batch)
        for idx, att_w in enumerate(att_ws):
            filename = "%s/%s.ep.{.updater.epoch}.png" % (
                self.outdir, self.data[idx][0])
            if self.reverse:
                dec_len = int(self.data[idx][1]['input'][0]['shape'][0])
                enc_len = int(self.data[idx][1]['output'][0]['shape'][0])
            else:
                dec_len = int(self.data[idx][1]['output'][0]['shape'][0])
                enc_len = int(self.data[idx][1]['input'][0]['shape'][0])
            if len(att_w.shape) == 3:
                att_w = att_w[:, :dec_len, :enc_len]
            else:
                att_w = att_w[:dec_len, :enc_len]
            self._plot_and_save_attention(att_w, filename.format(trainer))

    def _plot_and_save_attention(self, att_w, filename):
        # dynamically import matplotlib due to not found error
        import matplotlib.pyplot as plt
        if len(att_w.shape) == 3:
            for h, aw in enumerate(att_w, 1):
                plt.subplot(1, len(att_w), h)
                plt.imshow(aw, aspect="auto")
                plt.xlabel("Encoder Index")
                plt.ylabel("Decoder Index")
        else:
            plt.imshow(att_w, aspect="auto")
            plt.xlabel("Encoder Index")
            plt.ylabel("Decoder Index")
        plt.tight_layout()
        plt.savefig(filename)
        plt.close()


# * -------------------- language model related -------------------- *
def load_labeldict(dict_file):
    labeldict = {'<blank>': 0}  # <blank>'s Id is 0
    for ln in open(dict_file, 'r').readlines():
        s, i = ln.split()
        labeldict[s] = int(i)
    if '<eos>' not in labeldict:
        labeldict['<eos>'] = len(labeldict)
    return labeldict
