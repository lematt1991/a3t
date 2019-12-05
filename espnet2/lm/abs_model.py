from abc import ABC
from abc import abstractmethod
from typing import Tuple

import torch

from espnet.nets.scorer_interface import ScorerInterface


class AbsLM(torch.nn.Module, ScorerInterface, ABC):
    """The abstract LM class

    To share the loss calculation way among different models,
    We uses delegate pattern here:
    The instance of this class should be passed to "LanguageModel"

    >>> from espnet2.lm.e2e import LanguageE2E
    >>> lm = AbsLM()
    >>> model = LanguageE2E(lm=lm)

    This "model" is one of mediator objects for "Task" class.

    """
    @abstractmethod
    def forward(self, input: torch.Tensor, hidden: torch.Tensor) \
            -> Tuple[torch.Tensor, torch.Tensor]:
        raise NotImplementedError
