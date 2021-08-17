import pytest
import torch

from espnet2.asr.postencoder.hugging_face_transformers_postencoder import (
    HuggingFaceTransformersPostEncoder,  # noqa: H301
)


@pytest.mark.parametrize(
    "model_name_or_path",
    [
        "bert-base-cased",
        "gpt2",
        "xlnet-base-cased",
        "t5-small",
        "facebook/bart-base",
        "microsoft/mpnet-base",
    ],
)
@pytest.mark.execution_timeout(30)
def test_transformers_forward(model_name_or_path):
    idim = 400
    postencoder = HuggingFaceTransformersPostEncoder(idim, model_name_or_path)
    x = torch.randn([4, 50, idim], requires_grad=True)
    x_lengths = torch.LongTensor([20, 5, 50, 15])
    y, y_lengths = postencoder(x, x_lengths)
    y.sum().backward()
    odim = postencoder.output_size()
    assert y.shape == torch.Size([4, 50, odim])
    assert torch.equal(y_lengths, x_lengths)


@pytest.mark.execution_timeout(30)
def test_reload_pretrained_parameters():
    postencoder = HuggingFaceTransformersPostEncoder(400, "t5-small")
    saved_param = postencoder.parameters().__next__().detach().clone()

    postencoder.parameters().__next__().data *= 0
    new_param = postencoder.parameters().__next__().detach().clone()
    assert not torch.equal(saved_param, new_param)

    postencoder.reload_pretrained_parameters()
    new_param = postencoder.parameters().__next__().detach().clone()
    assert torch.equal(saved_param, new_param)
