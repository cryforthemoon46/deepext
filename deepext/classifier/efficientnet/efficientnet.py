import torch.optim as optim
import torch
import torch.nn as nn
import numpy as np

from deepext.base.base_model import BaseModel
from deepext.utils.tensor_util import try_cuda
from .efficientnet_lib.model import EfficientNetPredictor


class EfficientNet(BaseModel):
    def __init__(self, num_classes, network='efficientnet-b0', lr=0.1, momentum=0.9, weight_decay=1e-4):
        super().__init__()
        self._num_classes = num_classes
        self._model = EfficientNetPredictor.from_name(network, override_params={'num_classes': self._num_classes})
        self._network = network
        self._optimizer = optim.SGD(
            self._model.parameters(), lr,
            momentum=momentum,
            weight_decay=weight_decay)
        self._criterion = torch.nn.CrossEntropyLoss()
        if torch.cuda.is_available():
            self._model.cuda()
            self._criterion.cuda()

    def train_batch(self, train_x: torch.Tensor, teacher: torch.Tensor) -> float:
        """
        :param train_x: (batch size, channel, height, width)
        :param teacher: (batch size, )
        """
        self._model.train()
        train_x = try_cuda(train_x).float()
        teacher = try_cuda(teacher).long()

        # compute output
        output = self._model(train_x)
        loss = self._criterion(output, teacher)
        # compute gradient and do SGD step
        self._optimizer.zero_grad()
        loss.backward()
        self._optimizer.step()
        return loss.item()

    def predict(self, inputs):
        """
        :param inputs: (batch size, channel, height, width)
        :return: (batch size, class)
        """
        self._model.eval()
        with torch.no_grad():
            inputs = try_cuda(inputs).float()
            output = nn.Softmax(dim=1)(self._model(inputs))
            pred_ids = output.cpu().numpy()
        return pred_ids

    def save_weight(self, save_path):
        dict_to_save = {
            'num_class': self._num_classes,
            'network': self._network,
            'state_dict': self._model.state_dict(),
            'optimizer': self._optimizer.state_dict(),
        }
        torch.save(dict_to_save, save_path)

    def load_weight(self, weight_path):
        params = torch.load(weight_path)
        print('The pretrained weight is loaded')
        print('Num classes: {}'.format(params['num_class']))
        self._num_classes = params['num_class']
        self._model.load_state_dict(params['state_dict'])
        self._optimizer.load_state_dict(params['optimizer'])
        self._network = params['network']
        return self

    def get_model_config(self):
        config = {}
        config['model_name'] = 'EfficientNet'
        config['num_classes'] = self._num_classes
        config['optimizer'] = self._optimizer.__class__.__name__
        config['network'] = self._network
        return config

    def get_optimizer(self):
        return self._optimizer
