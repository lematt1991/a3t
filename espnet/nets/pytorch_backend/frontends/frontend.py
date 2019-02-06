from typing import Tuple, List, Union

import numpy
import torch
import torch.nn as nn
from torch_complex.tensor import ComplexTensor

from espnet.nets.pytorch_backend.frontends.dnn_beamformer import DNN_MVDR
from espnet.nets.pytorch_backend.frontends.dnn_wpe import DNN_WPE


class Frontend(nn.Module):
    def __init__(self,
                 idim: int,
                 # WPE options
                 use_wpe: bool=False,
                 wtype: str='blstmp',
                 wlayers: int=3,
                 wunits: int=300,
                 wprojs: int=320,
                 wdropout_rate: float=0.0,
                 taps: int=5,
                 delay: int=3,
                 use_dnn_mask_for_wpe: bool=True,

                 # Beamformer options
                 use_beamformer: bool=False,
                 btype: str='blstmp',
                 blayers: int=3,
                 bunits: int=300,
                 bprojs: int=320,
                 badim: int=320,
                 ref_channel: int=None,
                 bdropout_rate=0.0):
        super().__init__()

        self.use_beamformer = use_beamformer
        self.use_wpe = use_wpe
        self.use_dnn_mask_for_wpe = use_dnn_mask_for_wpe

        if self.use_wpe:
            if self.use_dnn_mask_for_wpe:
                iterations = 1
            else:
                # Performing as conventional WPE, without DNN Estimator
                iterations = 2

            self.wpe = DNN_WPE(wtype=wtype,
                               widim=idim,
                               wunits=wunits,
                               wprojs=wprojs,
                               wlayers=wlayers,
                               taps=taps,
                               delay=delay,
                               dropout_rate=wdropout_rate,
                               iterations=iterations,
                               use_dnn_mask=use_dnn_mask_for_wpe)
        else:
            self.wpe = None

        if self.use_beamformer:
            self.beamformer = DNN_MVDR(btype=btype,
                                       bidim=idim,
                                       bunits=bunits,
                                       bprojs=bprojs,
                                       blayers=blayers,
                                       dropout_rate=bdropout_rate,
                                       badim=badim,
                                       ref_channel=ref_channel)
        else:
            self.beamformer = None

    def forward(self, x: ComplexTensor,
                ilens: Union[torch.LongTensor, numpy.ndarray, List[int]])\
            -> Tuple[ComplexTensor, torch.LongTensor]:
        assert len(x) == len(ilens), (len(x), len(ilens))
        # (B, T, F) or (B, T, C, F)
        if x.dim() not in (3, 4):
            raise ValueError(f'Input dim must be 3 or 4: {x.dim()}')
        if not torch.is_tensor(ilens):
            ilens = torch.from_numpy(numpy.asarray(ilens)).to(x.device)

        h = x
        if h.dim() == 4:
            if self.training and self.use_beamformer \
                    and self.use_wpe and self.use_dnn_mask_for_wpe:
                # Select one from DNN-WPE and DNN-Beamformer
                true_false = [True, False]
                numpy.random.shuffle(true_false)
                use_wpe, use_beamformer = true_false

            else:
                use_wpe = self.use_wpe
                use_beamformer = self.use_beamformer

            # 1. WPE
            if use_wpe:
                # h: (B, T, C, F) -> h: (B, T, C, F)
                h, ilens = self.wpe(h, ilens)

            # 2. Beamformer
            if use_beamformer:
                # h: (B, T, C, F) -> h: (B, T, F)
                h, ilens = self.beamformer(h, ilens)

        return h, ilens


def frontend_for(args, idim):
    return Frontend(
        idim=idim,
        # WPE options
        use_wpe=args.use_wpe,
        wtype=args.wtype,
        wlayers=args.wlayers,
        wunits=args.wunits,
        wprojs=args.wprojs,
        wdropout_rate=args.wdropout_rate,
        taps=args.taps,
        delay=args.delay,
        use_dnn_mask_for_wpe=args.use_dnn_mask_for_wpe,

        # Beamformer options
        use_beamformer=args.use_beamformer,
        btype=args.btype,
        blayers=args.blayers,
        bunits=args.bunits,
        bprojs=args.bprojs,
        badim=args.badim,
        ref_channel=args.ref_channel,
        bdropout_rate=args.bdropout_rate)
