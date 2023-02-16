import os
import sys
from typing import Tuple, Dict

import cv2
import torch
import numpy as np
from ultralytics.yolo.utils import ops
from openvino.runtime import Core, Model
from ultralytics.yolo.utils.plotting import colors
#from ultralytics import YOLO

SCRIPT_DIR = os.path.dirname(os.path.abspath("models/object_detection/yolov8n"))
sys.path.append(os.path.dirname(SCRIPT_DIR))

# custom labels. there is no other way since streamlit issuing thread error or import YOLO
label_map = {0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle', 4: 'airplane', 5: 'bus', 6: 'train', 7: 'truck', 8: 'boat', 9: 'traffic light', 10: 'fire hydrant', 11: 'stop sign', 12: 'parking meter', 13: 'bench', 14: 'bird', 15: 'cat', 16: 'dog', 17: 'horse', 18: 'sheep', 19: 'cow', 20: 'elephant', 21: 'bear', 22: 'zebra', 23: 'giraffe', 24: 'backpack', 25: 'umbrella', 26: 'handbag', 27: 'tie', 28: 'suitcase', 29: 'frisbee', 30: 'skis', 31: 'snowboard', 32: 'sports ball', 33: 'kite', 34: 'baseball bat', 35: 'baseball glove', 36: 'skateboard', 37: 'surfboard', 38: 'tennis racket', 39: 'bottle', 40: 'wine glass', 41: 'cup', 42: 'fork', 43: 'knife', 44: 'spoon', 45: 'bowl', 46: 'banana', 47: 'apple', 48: 'sandwich', 49: 'orange', 50: 'broccoli', 51: 'carrot', 52: 'hot dog', 53: 'pizza', 54: 'donut', 55: 'cake', 56: 'chair', 57: 'couch', 58: 'potted plant', 59: 'bed', 60: 'dining table', 61: 'toilet', 62: 'tv', 63: 'laptop', 64: 'mouse', 65: 'remote', 66: 'keyboard', 67: 'cell phone', 68: 'microwave', 69: 'oven', 70: 'toaster', 71: 'sink', 72: 'refrigerator', 73: 'book', 74: 'clock', 75: 'vase', 76: 'scissors', 77: 'teddy bear', 78: 'hair drier', 79: 'toothbrush'}

class YOLOv8:
  def __init__(self, device=None, model="yolov8"):
    ie = Core()
    model_xml = f"{SCRIPT_DIR}/yolov8n/yolov8n.xml"
    model = ie.read_model(model=model_xml)
    """
    if device is None:
      self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
      self.device = device
      if self.device != "cpu":
        model.reshape({0: [1, 3, 640, 640]})
    """
    self.device = "CPU"
    self.compiled_model = ie.compile_model(model, self.device)
    #self.label_map = YOLO("yolov8n_openvino_model/yolov8n.pt").model.names

  def __repr__(self):
    return "yolov8"

  def detect_batch(self, images, threshold=None):
    results = []

    for image in images:
      input_image = np.asarray(image)
      num_outputs = len(self.compiled_model.outputs)
      preprocessed_image = self.preprocess_image(input_image)
      input_tensor = self.image_to_tensor(preprocessed_image)
      result = self.compiled_model(input_tensor)
      boxes = result[self.compiled_model.output(0)]
      masks = None
      if num_outputs > 1:
        masks = result[self.compiled_model.output(1)]
      input_hw = input_tensor.shape[2:]
      detections = self.postprocess(pred_boxes=boxes, input_hw=input_hw, orig_img=input_image, pred_masks=masks)
      image_with_boxes = self.draw_results(detections, input_image, label_map)
      results.append(image_with_boxes)
    return results

  def letterbox(self, img, new_shape = (640, 640), color = (114, 114, 114), auto:bool = False, scale_fill:bool = False, scaleup:bool = False, stride:int = 32):
    # Resize and pad image while meeting stride-multiple constraints
    shape = img.shape[:2]  # current shape [height, width]
    if isinstance(new_shape, int):
      new_shape = (new_shape, new_shape)

    # Scale ratio (new / old)
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    if not scaleup:  # only scale down, do not scale up (for better test mAP)
      r = min(r, 1.0)

    # Compute padding
    ratio = r, r  # width, height ratios
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]  # wh padding
    if auto:  # minimum rectangle
      dw, dh = np.mod(dw, stride), np.mod(dh, stride)  # wh padding
    elif scale_fill:  # stretch
      dw, dh = 0.0, 0.0
      new_unpad = (new_shape[1], new_shape[0])
      ratio = new_shape[1] / shape[1], new_shape[0] / shape[0]  # width, height ratios

    dw /= 2  # divide padding into 2 sides
    dh /= 2

    if shape[::-1] != new_unpad:  # resize
      img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)  # add border
    return img, ratio, (dw, dh)

  def preprocess_image(self, img0):
    # Preprocess image according to YOLOv8 input requirements
    # resize
    img = self.letterbox(img0)[0]
    # Convert HWC to CHW
    img = img.transpose(2, 0, 1)
    img = np.ascontiguousarray(img)
    return img

  def image_to_tensor(self, image:np.ndarray):
    input_tensor = image.astype(np.float32)  # uint8 to fp32
    input_tensor /= 255.0  # 0 - 255 to 0.0 - 1.0

    # add batch dimension
    if input_tensor.ndim == 3:
      input_tensor = np.expand_dims(input_tensor, 0)
    return input_tensor

  def postprocess(self,
    pred_boxes,
    input_hw,
    orig_img,
    min_conf_threshold = 0.25,
    nms_iou_threshold = 0.7,
    agnosting_nms = False,
    max_detections = 300,
    pred_masks = None,
    retina_mask = False
  ):
    """
    YOLOv8 model postprocessing function. Applied non maximum supression algorithm to detections and rescale boxes to original image size
    Parameters:
        pred_boxes (np.ndarray): model output prediction boxes
        input_hw (np.ndarray): preprocessed image
        orig_image (np.ndarray): image before preprocessing
        min_conf_threshold (float, *optional*, 0.25): minimal accepted confidence for object filtering
        nms_iou_threshold (float, *optional*, 0.45): minimal overlap score for removing objects duplicates in NMS
        agnostic_nms (bool, *optiona*, False): apply class agnostinc NMS approach or not
        max_detections (int, *optional*, 300):  maximum detections after NMS
        pred_masks (np.ndarray, *optional*, None): model ooutput prediction masks, if not provided only boxes will be postprocessed
        retina_mask (bool, *optional*, False): retina mask postprocessing instead of native decoding
    Returns:
       pred (List[Dict[str, np.ndarray]]): list of dictionary with det - detected boxes in format [x1, y1, x2, y2, score, label] and segment - segmentation polygons for each element in batch
    """
    nms_kwargs = {"agnostic": agnosting_nms, "max_det":max_detections}
    if pred_masks is not None:
      nms_kwargs["nm"] = 32
    preds = ops.non_max_suppression(
      torch.from_numpy(pred_boxes),
      min_conf_threshold,
      nms_iou_threshold,
      **nms_kwargs
    )
    results = []
    proto = torch.from_numpy(pred_masks) if pred_masks is not None else None

    for i, pred in enumerate(preds):
      shape = orig_img[i].shape if isinstance(orig_img, list) else orig_img.shape
      if not len(pred):
        results.append({"det": [], "segment": []})
        continue
      if proto is None:
        pred[:, :4] = ops.scale_boxes(input_hw, pred[:, :4], shape).round()
        results.append({"det": pred})
        continue
      if retina_mask:
        pred[:, :4] = ops.scale_boxes(input_hw, pred[:, :4], shape).round()
        masks = ops.process_mask_native(proto[i], pred[:, 6:], pred[:, :4], shape[:2])  # HWC
        segments = [ops.scale_segments(input_hw, x, shape, normalize=False) for x in ops.masks2segments(masks)]
      else:
        masks = ops.process_mask(proto[i], pred[:, 6:], pred[:, :4], input_hw, upsample=True)  # HWC
        pred[:, :4] = ops.scale_boxes(input_hw, pred[:, :4], shape).round()
        segments = [ops.scale_segments(input_hw, x, shape, normalize=False) for x in ops.masks2segments(masks)]
      results.append({"det": pred[:, :6].numpy(), "segment": segments})
    return results

  def draw_results(self, results:Dict, source_image:np.ndarray, label_map:Dict):
    """
    Helper function for drawing bounding boxes on image
    Parameters:
        image_res (np.ndarray): detection predictions in format [x1, y1, x2, y2, score, label_id]
        source_image (np.ndarray): input image for drawing
        label_map; (Dict[int, str]): label_id to class name mapping
    Returns:

    """
    boxes = results[0]["det"]
    masks = results[0].get("segment")
    for idx, (*xyxy, conf, lbl) in enumerate(boxes):
        label = f'{label_map[int(lbl)]} {conf:.2f}'
        mask = masks[idx] if masks is not None else None

        source_image = self.plot_one_box(xyxy, source_image, mask=mask, label=label, color=colors(int(lbl)), line_thickness=1)
    return source_image

  def plot_one_box(self, box:np.ndarray, img:np.ndarray, color:Tuple[int, int, int] = None, mask:np.ndarray = None, label:str = None, line_thickness:int = 5):
    """
    Helper function for drawing single bounding box on image
    Parameters:
        x (np.ndarray): bounding box coordinates in format [x1, y1, x2, y2]
        img (no.ndarray): input image
        color (Tuple[int, int, int], *optional*, None): color in BGR format for drawing box, if not specified will be selected randomly
        mask (np.ndarray, *optional*, None): instance segmentation mask polygon in format [N, 2], where N - number of points in contour, if not provided, only box will be drawn
        label (str, *optonal*, None): box label string, if not provided will not be provided as drowing result
        line_thickness (int, *optional*, 5): thickness for box drawing lines
    """
    # Plots one bounding box on image img
    tl = line_thickness or round(0.002 * (img.shape[0] + img.shape[1]) / 2) + 1  # line/font thickness
    color = color or [random.randint(0, 255) for _ in range(3)]
    c1, c2 = (int(box[0]), int(box[1])), (int(box[2]), int(box[3]))
    cv2.rectangle(img, c1, c2, color, thickness=tl, lineType=cv2.LINE_AA)
    if label:
        tf = max(tl - 1, 1)  # font thickness
        t_size = cv2.getTextSize(label, 0, fontScale=tl / 3, thickness=tf)[0]
        c2 = c1[0] + t_size[0], c1[1] - t_size[1] - 3
        cv2.rectangle(img, c1, c2, color, -1, cv2.LINE_AA)  # filled
        cv2.putText(img, label, (c1[0], c1[1] - 2), 0, tl / 3, [225, 255, 255], thickness=tf, lineType=cv2.LINE_AA)
    if mask is not None:
        image_with_mask = img.copy()
        cv2.fillPoly(image_with_mask, pts=[mask.astype(int)], color=color)
        img = cv2.addWeighted(img, 0.5, image_with_mask, 0.5, 1)
    return img