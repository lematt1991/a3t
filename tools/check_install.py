#!/usr/bin/env python

# Copyright 2018 Nagoya University (Tomoki Hayashi)
#  Apache 2.0  (http://www.apache.org/licenses/LICENSE-2.0)

import argparse
import importlib
import logging
import sys

# you should add the libraries which are not included in requirements.txt
MANUALLY_INSTALLED_LIBRARIES = [
    ('matplotlib', None),
    ('chainer_ctc', None),
    ('warpctc_pytorch', None)
]

parser = argparse.ArgumentParser()
parser.add_argument('--requirements', '-r', default='./requirements.txt', type=str,
                    help='requirements.txt')
args = parser.parse_args()

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s")

logging.info("python version = " + sys.version)

# load requirements
with open(args.requirements, 'r') as f:
    lines = f.readlines()

# parse requirements
library_list = []
for line in lines:
    line = line.replace('\n', '')
    if '==' in line:
        name, version = line.split('==')
    elif '>=' in line:
        name, _ = line.split('>=')
        version = None
    else:
        name = line
        version = None
    library_list.append((name, version))

# add some library manually
library_list.extend(MANUALLY_INSTALLED_LIBRARIES)

# chech library availableness
logging.info("library availableness check start.")
logging.info("# libraries to be checked = %d" % len(library_list))
is_collect_installed_list = [None] * len(library_list)
for idx, (name, version) in enumerate(library_list):
    try:
        importlib.import_module(name)
        logging.info("--> %s is installed." % name)
        is_collect_installed_list[idx] = True
    except ImportError:
        logging.warn("--> %s is not installed." % name)
        is_collect_installed_list[idx] = False
    if version is not None:
        try:
            lib = importlib.import_module(name)
            assert lib.__version__ == version
            logging.info("--> %s version is matched." % name)
            is_collect_installed_list[idx] = True
        except AssertionError:
            logging.warn("--> %s version is not matched. please install %s==%s." % (name, name, version))
            is_collect_installed_list[idx] = False
logging.info("library availableness check done.")
logging.info("%d / %d libraries are correctly installed." % (
    sum(is_collect_installed_list), len(library_list)))

# check cuda availableness
if len(library_list) != sum(is_collect_installed_list):
    logging.info("please try to setup again and then re-run this script.")
else:
    logging.info("cuda availableness check start.")
    import chainer
    import torch
    try:
        assert torch.cuda.is_available()
        logging.info("--> cuda is available in torch.")
    except AssertionError:
        logging.warn("--> it seems that cuda is not available in torch.")
    try:
        assert torch.backends.cudnn.is_available()
        logging.info("--> cudnn is available in torch.")
    except AssertionError:
        logging.warn("--> it seems that cudnn is not available in torch.")
    try:
        assert chainer.backends.cuda.available
        logging.info("--> cuda is available in chainer.")
    except AssertionError:
        logging.warn("--> it seems that cuda is not available in chainer.")
    try:
        assert chainer.backends.cuda.cudnn_enabled
        logging.info("--> cudnn is available in chainer.")
    except AssertionError:
        logging.warn("--> it seems that cudnn is not available in chainer.")
    try:
        from cupy.cuda import nccl  # NOQA
        logging.info("--> nccl is installed.")
    except ImportError:
        logging.warn("--> it seems that nccl is not installed. multi-gpu is not enabled.")
        logging.warn("--> if you want to use multi-gpu, please install it and then re-setup.")
    try:
        assert torch.cuda.device_count() > 1
        logging.info("--> multi-gpu is available (#gpus = %d)." % torch.cuda.device_count())
    except AssertionError:
        logging.warn("--> it seems that only single gpu is available.")
        logging.warn('--> maybe your machine has only one gpu.')
    logging.info("cuda availableness check done.")
