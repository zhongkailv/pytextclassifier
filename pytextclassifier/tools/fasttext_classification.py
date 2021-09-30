# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: 
"""
import argparse
import pandas as pd
import os
import numpy as np
import time
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn import metrics
from datetime import timedelta
from sklearn.model_selection import train_test_split
import pickle
from tqdm import tqdm

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
MAX_VOCAB_SIZE = 10000  # 词表长度限制
UNK = '[UNK]',  # 未知字
PAD = '[PAD]'  # padding符号

dropout = 0.5  # 随机失活
require_improvement = 1000  # 若超过1000batch效果还没提升，则提前结束训练
num_epochs = 20  # epoch数
batch_size = 64  # mini-batch大小
test_batch_size = 32
pad_size = 128  # 每句话处理成的长度(短填长切)
learning_rate = 1e-3  # 学习率
embed_size = 200  # 字向量维度
hidden_size = 256  # 隐藏层大小
n_gram_vocab = 250499  # ngram 词表大小


def load_data(data_filepath, header=None, delimiter='\t', names=['labels', 'text'], **kwargs):
    data_df = pd.read_csv(data_filepath, header=header, delimiter=delimiter, names=names, **kwargs)
    print(data_df.head())
    X, y = data_df['text'], data_df['labels']
    print('loaded data list, X size: {}, y size: {}'.format(len(X), len(y)))
    assert len(X) == len(y)
    print('num_classes:%d' % len(set(y)))
    return X, y


def build_vocab(contents, tokenizer, max_size, min_freq):
    vocab_dic = {}
    for line in tqdm(contents):
        lin = line.strip()
        if not lin:
            continue
        content = lin.split('\t')[0]
        for word in tokenizer(content):
            vocab_dic[word] = vocab_dic.get(word, 0) + 1
    vocab_list = sorted([_ for _ in vocab_dic.items() if _[1] >= min_freq], key=lambda x: x[1], reverse=True)[
                 :max_size]
    vocab_dic = {word_count[0]: idx for idx, word_count in enumerate(vocab_list)}
    vocab_dic.update({UNK: len(vocab_dic), PAD: len(vocab_dic) + 1})
    return vocab_dic


def build_dataset(X, y, vocab_path, label_vocab_path, pad_size=128):
    if os.path.exists(vocab_path):
        word_id_map = pickle.load(open(vocab_path, 'rb'))
    else:
        word_id_map = build_vocab(X, tokenizer=tokenizer, max_size=MAX_VOCAB_SIZE, min_freq=1)
        pickle.dump(word_id_map, open(vocab_path, 'wb'))
    print(f"word vocab size: {len(word_id_map)}")

    if os.path.exists(label_vocab_path):
        label_id_map = pickle.load(open(label_vocab_path, 'rb'))
    else:
        id_label_map = {id: v for id, v in enumerate(set(y.tolist()))}
        label_id_map = {v: k for k, v in id_label_map.items()}
        pickle.dump(label_id_map, open(label_vocab_path, 'wb'))
    print(f"label vocab size: {len(label_id_map)}")

    def biGramHash(sequence, t, buckets):
        t1 = sequence[t - 1] if t - 1 >= 0 else 0
        return (t1 * 14918087) % buckets

    def triGramHash(sequence, t, buckets):
        t1 = sequence[t - 1] if t - 1 >= 0 else 0
        t2 = sequence[t - 2] if t - 2 >= 0 else 0
        return (t2 * 14918087 * 18408749 + t1 * 14918087) % buckets

    def load_dataset(X, y, pad_size=128):
        contents = []
        for content, label in zip(X, y):
            words_line = []
            token = tokenizer(content)
            seq_len = len(token)
            if pad_size:
                if len(token) < pad_size:
                    token.extend([PAD] * (pad_size - len(token)))
                else:
                    token = token[:pad_size]
                    seq_len = pad_size
            # word to id
            for word in token:
                words_line.append(word_id_map.get(word, word_id_map.get(UNK)))
            label_id = label_id_map.get(label)
            # fasttext ngram
            buckets = n_gram_vocab
            bigram = []
            trigram = []
            # ------ngram------
            for i in range(pad_size):
                bigram.append(biGramHash(words_line, i, buckets))
                trigram.append(triGramHash(words_line, i, buckets))
            # -----------------
            contents.append((words_line, label_id, seq_len, bigram, trigram))
        return contents

    data = load_dataset(X, y, pad_size)
    return data, word_id_map, label_id_map


class DatasetIterater:
    def __init__(self, batches, batch_size, device):
        self.batch_size = batch_size
        self.batches = batches
        self.n_batches = len(batches) // batch_size if len(batches) > batch_size else 1
        self.residue = False  # 记录batch数量是否为整数
        if len(batches) % self.n_batches != 0:
            self.residue = True
        self.index = 0
        self.device = device

    def _to_tensor(self, datas):
        x = torch.LongTensor([_[0] for _ in datas]).to(self.device)
        y = torch.LongTensor([_[1] for _ in datas]).to(self.device)
        bigram = torch.LongTensor([_[3] for _ in datas]).to(self.device)
        trigram = torch.LongTensor([_[4] for _ in datas]).to(self.device)

        # pad前的长度(超过pad_size的设为pad_size)
        seq_len = torch.LongTensor([_[2] for _ in datas]).to(self.device)
        return (x, seq_len, bigram, trigram), y

    def __next__(self):
        if self.residue and self.index == self.n_batches:
            batches = self.batches[self.index * self.batch_size: len(self.batches)]
            self.index += 1
            batches = self._to_tensor(batches)
            return batches

        elif self.index >= self.n_batches:
            self.index = 0
            raise StopIteration
        else:
            batches = self.batches[self.index * self.batch_size: (self.index + 1) * self.batch_size]
            self.index += 1
            batches = self._to_tensor(batches)
            return batches

    def __iter__(self):
        return self

    def __len__(self):
        if self.residue:
            return self.n_batches + 1
        else:
            return self.n_batches


def build_iterator(dataset, batch_size, device):
    iter = DatasetIterater(dataset, batch_size, device)
    return iter


class FastTextModel(nn.Module):
    """Bag of Tricks for Efficient Text Classification"""

    def __init__(self, vocab_size, num_classes):
        super(FastTextModel, self).__init__()
        self.embedding = nn.Embedding(vocab_size, embed_size, padding_idx=vocab_size - 1)
        self.embedding_ngram2 = nn.Embedding(n_gram_vocab, embed_size)
        self.embedding_ngram3 = nn.Embedding(n_gram_vocab, embed_size)
        self.dropout = nn.Dropout(dropout)
        self.fc1 = nn.Linear(embed_size * 3, hidden_size)
        self.fc2 = nn.Linear(hidden_size, num_classes)

    def forward(self, x):
        out_word = self.embedding(x[0])
        out_bigram = self.embedding_ngram2(x[2])
        out_trigram = self.embedding_ngram3(x[3])
        out = torch.cat((out_word, out_bigram, out_trigram), -1)

        out = out.mean(dim=1)
        out = self.dropout(out)
        out = self.fc1(out)
        out = F.relu(out)
        out = self.fc2(out)
        return out


# 权重初始化，默认xavier
def init_network(model, method='xavier', exclude='embedding'):
    for name, w in model.named_parameters():
        if exclude not in name:
            if 'weight' in name:
                if method == 'xavier':
                    nn.init.xavier_normal_(w)
                elif method == 'kaiming':
                    nn.init.kaiming_normal_(w)
                else:
                    nn.init.normal_(w)
            elif 'bias' in name:
                nn.init.constant_(w, 0)
            else:
                pass


def get_time_dif(start_time):
    """获取已使用时间"""
    end_time = time.time()
    time_dif = end_time - start_time
    return timedelta(seconds=int(round(time_dif)))


def evaluate(model, data_iter):
    model.eval()
    loss_total = 0
    predict_all = np.array([], dtype=int)
    labels_all = np.array([], dtype=int)
    with torch.no_grad():
        for texts, labels in data_iter:
            outputs = model(texts)
            loss = F.cross_entropy(outputs, labels)
            loss_total += loss
            labels = labels.cpu().numpy()
            predic = torch.max(outputs, 1)[1].cpu().numpy()
            labels_all = np.append(labels_all, labels)
            predict_all = np.append(predict_all, predic)
        print(f"evaluate, last batch, y_true: {labels}, y_pred: {predic}")
    acc = metrics.accuracy_score(labels_all, predict_all)
    return acc, loss_total / len(data_iter)


def train(model, train_iter, dev_iter, num_epochs, learning_rate, require_improvement, save_path):
    # train
    start_time = time.time()
    model.train()
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    total_batch = 0  # 记录进行到多少batch
    dev_best_loss = float('inf')
    last_improve = 0  # 记录上次验证集loss下降的batch数
    flag = False  # 记录是否很久没有效果提升
    for epoch in range(num_epochs):
        print('Epoch [{}/{}]'.format(epoch + 1, num_epochs))
        # scheduler.step() # 学习率衰减
        for i, (trains, labels) in enumerate(train_iter):
            outputs = model(trains)
            model.zero_grad()
            loss = F.cross_entropy(outputs, labels)
            loss.backward()
            optimizer.step()
            if total_batch % 100 == 0:
                # 输出在训练集和验证集上的效果
                y_true = labels.cpu()
                y_pred = torch.max(outputs, 1)[1].cpu()
                train_acc = metrics.accuracy_score(y_true, y_pred)
                dev_acc, dev_loss = evaluate(model, dev_iter)
                if dev_loss < dev_best_loss:
                    dev_best_loss = dev_loss
                    torch.save(model.state_dict(), save_path)
                    improve = '*'
                    last_improve = total_batch
                else:
                    improve = ''
                time_dif = get_time_dif(start_time)
                msg = 'Iter: {0:>6},  Train Loss: {1:>5.2},  Train Acc: {2:>6.2%},  Val Loss: {3:>5.2},  Val Acc: {4:>6.2%},  Time: {5} {6}'
                print(msg.format(total_batch, loss.item(), train_acc, dev_loss, dev_acc, time_dif, improve))
                model.train()
            total_batch += 1
            if total_batch - last_improve > require_improvement:
                # 验证集loss超过1000batch没下降，结束训练
                print("No optimization for a long time, auto-stopping...")
                flag = True
                break
        if flag:
            break


def load_model(model, model_path):
    model.load_state_dict(torch.load(model_path))
    return model


def predict(model, data_list, label_id_map):
    model.eval()

    def biGramHash(sequence, t, buckets):
        t1 = sequence[t - 1] if t - 1 >= 0 else 0
        return (t1 * 14918087) % buckets

    def triGramHash(sequence, t, buckets):
        t1 = sequence[t - 1] if t - 1 >= 0 else 0
        t2 = sequence[t - 2] if t - 2 >= 0 else 0
        return (t2 * 14918087 * 18408749 + t1 * 14918087) % buckets

    def load_dataset(X, pad_size=128):
        contents = []
        for content in X:
            words_line = []
            token = tokenizer(content)
            seq_len = len(token)
            if pad_size:
                if len(token) < pad_size:
                    token.extend([PAD] * (pad_size - len(token)))
                else:
                    token = token[:pad_size]
                    seq_len = pad_size
            # word to id
            for word in token:
                words_line.append(word_id_map.get(word, word_id_map.get(UNK)))
            # fasttext ngram
            buckets = n_gram_vocab
            bigram = []
            trigram = []
            # ------ngram------
            for i in range(pad_size):
                bigram.append(biGramHash(words_line, i, buckets))
                trigram.append(triGramHash(words_line, i, buckets))
            # -----------------
            contents.append((words_line, 0, seq_len, bigram, trigram))
        return contents

    data = load_dataset(data_list, pad_size)
    data_iter = build_iterator(data, test_batch_size, device)
    # predict proba
    predict_all = np.array([], dtype=int)
    with torch.no_grad():
        for texts, _ in data_iter:
            outputs = model(texts)
            predic = torch.max(outputs, 1)[1].detach().cpu().numpy()
            predict_all = np.append(predict_all, predic)
    id_label_map = {v: k for k, v in label_id_map.items()}
    res = [id_label_map.get(i) for i in predict_all]
    return res


def get_args():
    parser = argparse.ArgumentParser(description='Text Classification')
    parser.add_argument('--model_dir', default='fasttext', type=str, help='save model dir')
    parser.add_argument('--data_path', default='../../examples/THUCNews/data/train.txt', type=str,
                        help='sample data file path')
    args = parser.parse_args()
    print(args)
    return args


if __name__ == '__main__':
    args = get_args()
    model_dir = args.model_dir
    if model_dir and not os.path.exists(model_dir):
        os.makedirs(model_dir)
    tokenizer = lambda x: [y for y in x]  # char-level
    SEED = 1
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED) # 保持结果一致
    print(f'device: {device}')
    # load data
    X, y = load_data(args.data_path)
    word_vocab_path = os.path.join(model_dir, 'word_vocab.pkl')
    label_vocab_path = os.path.join(model_dir, 'label_vocab.pkl')
    save_model_path = os.path.join(model_dir, 'model.pth')
    data, word_id_map, label_id_map = build_dataset(X, y, word_vocab_path, label_vocab_path, pad_size)
    train_data, dev_data = train_test_split(data, test_size=0.1, random_state=SEED)
    train_iter = build_iterator(train_data, batch_size, device)
    dev_iter = build_iterator(dev_data, batch_size, device)
    # create model
    vocab_size = len(word_id_map)
    num_classes = len(set(y.tolist()))
    model = FastTextModel(vocab_size, num_classes).to(device)
    init_network(model)
    print(model.parameters)
    # train model
    train(model, train_iter, dev_iter, num_epochs, learning_rate, require_improvement, save_model_path)
    # predict
    new_model = load_model(model, save_model_path)
    preds = predict(new_model, X[:10], label_id_map)
    for text, pred in zip(X[:10], preds):
        print(text, pred)