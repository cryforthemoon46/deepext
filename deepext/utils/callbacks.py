from torchvision.transforms import ToPILImage
from torch.utils.data import Dataset
import torch
import math
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

from .image_utils import *
from ..base import SegmentationModel, BaseModel, DetectionModel
from ..classifier import AttentionBranchNetwork


class GenerateSegmentationImageCallback:
    def __init__(self, model: SegmentationModel, output_dir: str, per_epoch: int, dataset: Dataset, alpha=150,
                 color_palette_ls: List[int] = None):
        self._model: SegmentationModel = model
        self._output_dir = output_dir
        self._per_epoch = per_epoch
        self._dataset = dataset
        self._alpha = alpha
        self._to_pil = ToPILImage()
        self._color_palette = color_palette_ls or default_color_palette()

    def __call__(self, epoch: int):
        if (epoch + 1) % self._per_epoch != 0:
            return
        data_len = len(self._dataset)
        random_image_index = np.random.randint(0, data_len)
        img_tensor, _ = self._dataset[random_image_index]

        result_img = self._model.draw_predicted_result(img_tensor, img_size_for_model=img_tensor.shape[1:],
                                                       color_palette=self._color_palette)
        result_img.save(
            f"{self._output_dir}/result_image{epoch + 1}.png")


class LearningRateScheduler:
    def __init__(self, max_epoch: int, power=0.9):
        self._max_epoch = max_epoch
        self._power = power

    def __call__(self, epoch: int):
        return math.pow((1 - epoch / self._max_epoch), self._power)


class WarmUpLRScheduler:
    def __init__(self, warmup_lr=1e-2, lr=1e-4, warmup_epochs=10):
        """
        :param warmup_lr: Warm up中の学習率
        :param lr: Warm up終了後の学習率
        :param warmup_epochs: 何エポックまでをWarm up期間とするか
        """
        self._warmup_lr = warmup_lr
        self._warmup_epochs = warmup_epochs
        self._lr = lr

    def __call__(self, epoch: int):
        return self._warmup_lr if epoch < self._warmup_epochs else self._lr


class GenerateAttentionMapCallback:
    def __init__(self, output_dir: str, per_epoch: int, dataset: Dataset, model: AttentionBranchNetwork):
        self._out_dir, self._per_epoch, self._dataset = output_dir, per_epoch, dataset
        self._model = model
        self._to_pil = ToPILImage()

    def __call__(self, epoch: int):
        if (epoch + 1) % self._per_epoch != 0:
            return
        self._model.eval()
        data_len = len(self._dataset)
        random_image_index = np.random.randint(0, data_len)
        img_tensor, label = self._dataset[random_image_index]
        img_tensor = img_tensor.view(1, img_tensor.shape[0], img_tensor.shape[1], img_tensor.shape[2]).cuda()
        perception_pred, attention_pred, attention_map = self._model(img_tensor)
        pred_label = perception_pred.argmax(-1).item()

        img: Image.Image = self._to_pil(img_tensor.detach().cpu()[0])
        img.save(f"{self._out_dir}/epoch{epoch + 1}_t{label}_p{pred_label}.png")

        plt.figure()
        sns.heatmap(attention_map.cpu().detach().numpy()[0][0])
        plt.savefig(f"{self._out_dir}/epoch{epoch + 1}_attention.png")
        plt.close('all')


class VisualizeRandomObjectDetectionResult:
    def __init__(self, model: DetectionModel, img_size: Tuple[int, int], dataset: Dataset, out_dir: str,
                 label_names: List[str], per_epoch: int = 10, pred_color=(0, 0, 255), teacher_color=(0, 255, 0)):
        """
        :param model:
        :param img_size: (H, W)
        :param dataset:
        :param out_dir:
        :param per_epoch:
        :param pred_color:
        :param teacher_color:
        """
        self._model = model
        self._dataset = dataset
        self._pred_color = pred_color
        self._teacher_color = teacher_color
        self._per_epoch = per_epoch
        self._out_dir = out_dir
        self._img_size = img_size
        self._label_names = label_names

    def __call__(self, epoch: int):
        if (epoch + 1) % self._per_epoch != 0:
            return
        data_len = len(self._dataset)
        random_image_index = np.random.randint(0, data_len)
        image, teacher_bboxes = self._dataset[random_image_index]
        assert isinstance(image, torch.Tensor), "Expected image type is Tensor."
        result_img = self._model.draw_predicted_result(image, img_size_for_model=(image.shape[-2], image.shape[-1]),
                                                       label_names=self._label_names)
        image = self._draw_teacher_bboxes(result_img, teacher_bboxes=teacher_bboxes)
        cv2.imwrite(f"{self._out_dir}/result_{epoch + 1}.png", image)

    def _draw_teacher_bboxes(self, image: np.ndarray, teacher_bboxes: List[Tuple[float, float, float, float, int]]):
        """
        :param image:
        :param teacher_bboxes: List of [x_min, y_min, x_max, y_max, label]
        :return:
        """
        if teacher_bboxes is None or len(teacher_bboxes) == 0:
            return image
        for bbox in teacher_bboxes:
            image = draw_bounding_boxes_with_name_tag(image, [bbox], color=self._teacher_color,
                                                      text=self._label_names[bbox[-1]])
        return image


class ModelCheckout:
    def __init__(self, model: BaseModel, our_dir: str, per_epoch: int = 5):
        self._per_epoch = per_epoch
        self._out_dir = Path(our_dir)
        self._model = model
        if not self._out_dir.exists():
            self._out_dir.mkdir()

    def __call__(self, epoch: int):
        if (epoch + 1) % self._per_epoch != 0:
            return
        self._model.save_weight(str(self._out_dir.joinpath(f"{self._model.__class__.__name__}_ep{epoch + 1}.pth")))
