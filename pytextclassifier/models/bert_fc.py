# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: 
"""
import torch
import torch.nn as nn
from transformers import BertModel, BertTokenizer
import sys

sys.path.append('../..')
from pytextclassifier.utils.bert_utils import build_dataset, build_iterator
from pytextclassifier.bert_train_eval import init_network, train


class Config:
    """配置参数"""

    def __init__(self, dataset, embedding=None):
        self.model_name = 'bert_fc'
        self.train_path = dataset + '/data/train.txt'  # 训练集
        self.dev_path = dataset + '/data/dev.txt'  # 验证集
        self.test_path = dataset + '/data/test.txt'  # 测试集
        self.class_list = [x.strip() for x in open(
            dataset + '/data/class.txt').readlines()]  # 类别名单
        self.save_path = dataset + '/saved_dict/' + self.model_name + '.ckpt'  # 模型训练结果
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')  # 设备

        self.require_improvement = 1000  # 若超过1000batch效果还没提升，则提前结束训练
        self.num_classes = len(self.class_list)  # 类别数
        self.num_epochs = 3  # epoch数
        self.batch_size = 64  # mini-batch大小
        self.pad_size = 128  # 每句话处理成的长度(短填长切)
        self.learning_rate = 1e-3
        self.bert_path = 'bert-base-chinese'
        self.tokenizer = BertTokenizer.from_pretrained(self.bert_path)
        self.hidden_size = 512
        self.bert_hidden = 768
        self.dropout_rate = 0.1


class Model(nn.Module):
    """Bert + fc model"""

    def __init__(self, config):
        super(Model, self).__init__()
        self.bert = BertModel.from_pretrained(config.bert_path)
        for param in self.bert.parameters():
            param.requires_grad = True
        # dense layer (Output layer)
        self.fc = nn.Linear(config.bert_hidden, config.num_classes)

    def forward(self, x):
        # (x, seq_len, mask), y
        input_ids = x[0]  # batch size, seq max len
        input_mask = x[2]

        # (sequence_output, pooled_output) + encoder_outputs[1:]
        _, pooler_output = self.bert(input_ids=input_ids,
                                     attention_mask=input_mask,
                                     return_dict=False)
        out = self.fc(pooler_output)
        return out