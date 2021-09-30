# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: 
"""
import argparse
import pandas as pd
import os
import numpy as np
import pickle
import torch
from sklearn.model_selection import train_test_split
from simpletransformers.classification import ClassificationModel

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
os.environ["TOKENIZERS_PARALLELISM"] = "false"


def load_data(data_filepath, label_vocab_path, header=None, delimiter='\t', names=['labels', 'text'], **kwargs):
    data_df = pd.read_csv(data_filepath, header=header, delimiter=delimiter, names=names, **kwargs)
    X, y = data_df['text'], data_df['labels']
    print('loaded data list, X size: {}, y size: {}'.format(len(X), len(y)))
    assert len(X) == len(y)
    print('num_classes:%d' % len(set(y)))
    if os.path.exists(label_vocab_path):
        label_id_map = pickle.load(open(label_vocab_path, 'rb'))
    else:
        id_label_map = {id: v for id, v in enumerate(set(y.tolist()))}
        label_id_map = {v: k for k, v in id_label_map.items()}
        pickle.dump(label_id_map, open(label_vocab_path, 'wb'))
    print(f"label vocab size: {len(label_id_map)}")
    data_df['text'] = data_df['text'].astype(str)
    data_df['labels'] = data_df['labels'].map(lambda x: label_id_map.get(x))
    return data_df, label_id_map


class BertClassificationModel(ClassificationModel):
    """Bert + fc model"""

    def __init__(self, model_type='bert',
                 model_name='bert-base-chinese',
                 num_classes=10,
                 num_epochs=3,
                 batch_size=64,
                 max_seq_length=128,
                 model_dir='bert',
                 use_cuda=False
                 ):
        train_args = {
            "reprocess_input_data": True,
            "overwrite_output_dir": True,
            "output_dir": model_dir,
            "best_model_dir": f"{model_dir}/best_model",
            "max_seq_length": max_seq_length,
            "num_train_epochs": num_epochs,
            "train_batch_size": batch_size,
        }
        super(BertClassificationModel, self).__init__(model_name=model_name,
                                                      model_type=model_type,
                                                      num_labels=num_classes,
                                                      args=train_args,
                                                      use_cuda=use_cuda)


def load_model(model, model_path):
    model.load_state_dict(torch.load(model_path))
    return model


def get_args():
    parser = argparse.ArgumentParser(description='Bert Text Classification')
    parser.add_argument('--pretrain_model_type', default='bert', type=str,
                        help='pretrained huggingface model type')
    parser.add_argument('--pretrain_model_name', default='bert-base-chinese', type=str,
                        help='pretrained huggingface model name')
    parser.add_argument('--model_dir', default='bert', type=str, help='save model dir')
    parser.add_argument('--data_path', default='../../examples/THUCNews/data/train.txt', type=str,
                        help='sample data file path')
    parser.add_argument('--num_epochs', default=3, type=int, help='train epochs')
    parser.add_argument('--batch_size', default=64, type=int, help='train batch size')
    parser.add_argument('--max_seq_length', default=128, type=int, help='max seq length, trim longer sentence.')
    args = parser.parse_args()
    print(args)
    return args


if __name__ == '__main__':
    args = get_args()
    model_dir = args.model_dir
    if model_dir and not os.path.exists(model_dir):
        os.makedirs(model_dir)
    SEED = 1
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)  # 保持结果一致
    # load data
    label_vocab_path = os.path.join(model_dir, 'label_vocab.pkl')
    data_df, label_id_map = load_data(args.data_path, label_vocab_path)
    print(data_df.head())
    train_df, dev_df = train_test_split(data_df, test_size=0.1, random_state=SEED)
    # create model
    use_cuda = False if device == torch.device('cpu') else True
    print(f'device: {device}, use_cuda: {use_cuda}')
    model = BertClassificationModel(model_type=args.pretrain_model_type,
                                    model_name=args.pretrain_model_name,
                                    num_classes=len(label_id_map),
                                    num_epochs=args.num_epochs,
                                    batch_size=args.batch_size,
                                    max_seq_length=args.max_seq_length,
                                    model_dir=args.model_dir,
                                    use_cuda=use_cuda)
    print(model)
    # train model
    # Train and Evaluation data needs to be in a Pandas Dataframe,
    # it should contain a 'text' and a 'labels' column. text with type str, the label with type int.
    model.train_model(train_df)
    # Evaluate the model
    result, model_outputs, wrong_predictions = model.eval_model(dev_df)
    print('evaluate: ', result, model_outputs, wrong_predictions)
    # predict
    predictions, raw_outputs = model.predict(["就要性价比 惠普CQ40仅3800元抱回家"])
    print('pred:', predictions, ' raw_output:', raw_outputs)