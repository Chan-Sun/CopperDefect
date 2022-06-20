# Copyright (c) OpenMMLab. All rights reserved.
import argparse
import os.path as osp

import mmcv
import numpy as np
from mmcv import Config, DictAction
from mmdet.core.evaluation import eval_map
from mmdet.core.visualization import imshow_gt_det_bboxes,imshow_det_bboxes
from mmdet.datasets import build_dataset, get_loading_pipeline
import os
def bbox_map_eval(det_result, annotation):
    """Evaluate mAP of single image det result.

    Args:
        det_result (list[list]): [[cls1_det, cls2_det, ...], ...].
            The outer list indicates images, and the inner list indicates
            per-class detected bboxes.
        annotation (dict): Ground truth annotations where keys of
             annotations are:

            - bboxes: numpy array of shape (n, 4)
            - labels: numpy array of shape (n, )
            - bboxes_ignore (optional): numpy array of shape (k, 4)
            - labels_ignore (optional): numpy array of shape (k, )

    Returns:
        float: mAP
    """

    # use only bbox det result
    if isinstance(det_result, tuple):
        bbox_det_result = [det_result[0]]
    else:
        bbox_det_result = [det_result]
    # mAP
    iou_thrs = np.linspace(
        .5, 0.95, int(np.round((0.95 - .5) / .05)) + 1, endpoint=True)
    mean_aps = []
    for thr in iou_thrs:
        mean_ap, _ = eval_map(
            bbox_det_result, [annotation], iou_thr=thr, logger='silent')
        mean_aps.append(mean_ap)
    return sum(mean_aps) / len(mean_aps)


class ResultVisualizer:
    """Display and save evaluation results.

    Args:
        show (bool): Whether to show the image. Default: True
        wait_time (float): Value of waitKey param. Default: 0.
        score_thr (float): Minimum score of bboxes to be shown.
           Default: 0
    """

    def __init__(self, show=False, wait_time=0, score_thr=0):
        self.show = show
        self.wait_time = wait_time
        self.score_thr = score_thr

    def _save_image_gts_results(self, dataset, results, mAPs, out_dir=None):
        mmcv.mkdir_or_exist(out_dir)

        for mAP_info in mAPs:
            index, mAP = mAP_info
            data_info = dataset.prepare_train_img(index)

            # calc save file path
            filename = data_info['filename']
            if data_info['img_prefix'] is not None:
                filename = osp.join(data_info['img_prefix'], filename)
            else:
                filename = data_info['filename']
            fname, name = osp.splitext(osp.basename(filename))
            save_filename = fname+"_"+ str(round(mAP, 3))+"_"+ name
            out_file = osp.join(out_dir, save_filename)
            imshow_gt_det_bboxes(
                data_info['img'],
                data_info,
                results[index],
                dataset.CLASSES,
                show=self.show,
                gt_bbox_color='green',
                gt_mask_color='green',                
                gt_text_color=None,
                det_bbox_color="red",
                det_text_color=None,
                score_thr=self.score_thr,
                wait_time=self.wait_time,
                out_file=out_file)

    def _save_img_gt(self, dataset, out_dir=None,thickness=3,font_size=8,draw_label=True):
        mmcv.mkdir_or_exist(out_dir)
        for idx in range(len(dataset.img_ids)):
            data_info = dataset.prepare_train_img(idx)
            raw_img = data_info["img"]
            # calc save file path
            filename = data_info['filename']
            if data_info['img_prefix'] is not None:
                filename = osp.join(data_info['img_prefix'], filename)
            else:
                filename = data_info['filename']
            fname, name = osp.splitext(osp.basename(filename))
            out_file = osp.join(out_dir, data_info['ori_filename'])

            gt_bboxes = data_info['gt_bboxes']
            gt_labels = data_info['gt_labels']

            # img = mmcv.imread(img)

            img = imshow_det_bboxes(
                data_info["img"],
                gt_bboxes,
                gt_labels,
                None,
                class_names=dataset.CLASSES,
                bbox_color=dataset.PALETTE,
                text_color="green",
                mask_color=None,
                thickness=thickness,
                font_size=font_size,
                win_name="",
                show=False,
                out_file=out_file)

    def evaluate_and_show(self,
                          dataset,
                          results,
                          topk=20,
                          show_dir='work_dir',
                          eval_fn=None):
        """Evaluate and show results.

        Args:
            dataset (Dataset): A PyTorch dataset.
            results (list): Det results from test results pkl file
            topk (int): Number of the highest topk and
                lowest topk after evaluation index sorting. Default: 20
            show_dir (str, optional): The filename to write the image.
                Default: 'work_dir'
            eval_fn (callable, optional): Eval function, Default: None
        """

        assert topk > 0
        if (topk * 2) > len(dataset):
            topk = len(dataset) // 2

        if eval_fn is None:
            eval_fn = bbox_map_eval
        else:
            assert callable(eval_fn)

        prog_bar = mmcv.ProgressBar(len(results))
        _mAPs = {}
        for i, (result, ) in enumerate(zip(results)):
            # self.dataset[i] should not call directly
            # because there is a risk of mismatch
            data_info = dataset.prepare_train_img(i)
            mAP = eval_fn(result, data_info['ann_info'])
            _mAPs[i] = mAP
            prog_bar.update()

        # descending select topk image
        _mAPs = list(sorted(_mAPs.items(), key=lambda kv: kv[1]))
        good_mAPs = _mAPs[-topk:]
        bad_mAPs = _mAPs[:topk]

        good_dir = osp.abspath(osp.join(show_dir, 'good'))
        bad_dir = osp.abspath(osp.join(show_dir, 'bad'))
        self._save_image_gts_results(dataset, results, good_mAPs, good_dir)
        self._save_image_gts_results(dataset, results, bad_mAPs, bad_dir)

# def main(args):

#     mmcv.check_file_exist(args.prediction_path)

#     cfg = Config.fromfile(args.config)
#     if args.cfg_options is not None:
#         cfg.merge_from_dict(args.cfg_options)
#     cfg.data.test.test_mode = True

#     cfg.data.test.pop('samples_per_gpu', 0)
#     cfg.data.test.pipeline = get_loading_pipeline(cfg.data.train.pipeline)
#     dataset = build_dataset(cfg.data.test)
#     outputs = mmcv.load(args.prediction_path)

#     result_visualizer = ResultVisualizer(args.show, args.wait_time,
#                                          args.show_score_thr)
#     result_visualizer.evaluate_and_show(
#         dataset, outputs, topk=args.topk, show_dir=args.show_dir)


# for data in ["HRIPCB"]:
#     config_path = f"/home/user/sun_chen/Projects/CDFS_PCB/configs/{data}/frcn_baseline.py"
#     cfg = Config.fromfile(config_path)
#     cfg.data.test.test_mode = True
#     cfg.data.test.pop('samples_per_gpu', 0)
#     cfg.data.test.pipeline = get_loading_pipeline(cfg.data.train.pipeline) 

#     dataset = build_dataset(cfg.data.test)
#     visual = ResultVisualizer()
#     outdir = f"/home/user/sun_chen/Projects/CDFS_PCB/visualization/gt/{data}"

#     visual._save_img_gt(dataset, out_dir=outdir)
    
    
# for data in ["DeepPCB","HRIPCB"]:
#     config_path = f"/home/user/sun_chen/Projects/CDFS_PCB/configs/{data}/frcn_baseline.py"
#     cfg = Config.fromfile(config_path)
#     cfg.data.test.test_mode = True
#     cfg.data.test.pop('samples_per_gpu', 0)
#     cfg.data.test.pipeline = get_loading_pipeline(cfg.data.train.pipeline) 

#     dataset = build_dataset(cfg.data.test)
#     visual = ResultVisualizer()
#     outdir = f"/home/user/sun_chen/Projects/CDFS_PCB/visualization/gt/{data}"

#     visual._save_img_gt(dataset, out_dir=outdir)