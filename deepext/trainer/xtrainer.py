from typing import Tuple, List, Callable
import numpy as np
from torch.utils.data import DataLoader
from statistics import mean

from deepext.assemble.assemble_model import AssembleModel
from deepext.base import BaseModel
from deepext.assemble.learning_table import LearningTable
from deepext.utils.tensor_util import try_cuda


class XTrainer:
    def __init__(self, models: AssembleModel):
        self._assemble_model: AssembleModel = models

    def fit(self, learning_tables: List[LearningTable],
            metric_func_ls: List[Callable[[np.ndarray, np.ndarray], any]] = None,
            test_dataloader: DataLoader = None):
        assert len(learning_tables) == len(self._assemble_model.model_list)
        metric_func_ls = metric_func_ls or []
        for i in range(len(learning_tables)):
            learning_table = learning_tables[i]
            model = self._assemble_model.model_list[i]
            print(f"\n\nStart training model_{i}: {model.get_model_config()} \n\n")
            self.train_one_model(model, learning_table, test_dataloader, metric_func_ls)
        total_metric_str = ""
        for metric_func in metric_func_ls:
            metric = self.calc_metric(self._assemble_model, test_dataloader, metric_func)
            total_metric_str += f"{metric_func.__name__}: {metric} "
        print(f"\n\n\nTotal metrics  :  {total_metric_str}\n\n")

    def train_one_model(self, model: BaseModel, learning_table: LearningTable, test_dataloader: DataLoader,
                        metric_func_ls: List[Callable[[np.ndarray, np.ndarray], any]]):
        for epoch in range(learning_table.epochs):
            mean_loss = self.train_epoch(model, learning_table.data_loader)
            metric_str = ""
            for metric_func in metric_func_ls:
                metric = self.calc_metric(model, test_dataloader, metric_func)
                metric_str += f"{metric_func.__name__}: {metric} "
            print(f"epoch {epoch + 1} / {learning_table.epochs} --- loss: {mean_loss},  {metric_str}")
            callbacks = learning_table.callbacks or []
            for callback in callbacks:
                callback(epoch)

    def train_epoch(self, model: BaseModel, data_loader: DataLoader) -> float:
        loss_list = []
        for train_x, teacher in data_loader:
            train_x = try_cuda(train_x)
            teacher = try_cuda(teacher)
            loss = model.train_batch(train_x, teacher)
            loss_list.append(loss)
        return mean(loss_list)

    def calc_metric(self, model: BaseModel or AssembleModel, data_loader: DataLoader,
                    metric_func: Callable[[np.ndarray, np.ndarray], None]) -> float:
        metric_ls = []
        for x, teacher in data_loader:
            result = model.predict(x)
            metric_ls.append(metric_func(result, teacher.numpy()))
        return mean(metric_ls)