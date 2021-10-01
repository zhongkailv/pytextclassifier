# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: 
"""
import sys

sys.path.append('..')
from pytextclassifier import TextClassifier
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer

if __name__ == '__main__':
    vec = CountVectorizer(ngram_range=(1, 3))
    m = TextClassifier(model_name='lr')

    data = [
        ('education', '名师指导托福语法技巧：名词的复数形式'),
        ('education', '中国高考成绩海外认可 是“狼来了”吗？'),
        ('sports', '图文：法网孟菲尔斯苦战进16强 孟菲尔斯怒吼'),
        ('sports', '四川丹棱举行全国长距登山挑战赛 近万人参与'),
        ('sports', '米兰客场8战不败国米10年连胜')
    ]
    m.train(data)
    predict_label, predict_proba = m.predict(['福建春季公务员考试报名18日截止 2月6日考试',
                                              '意甲首轮补赛交战记录:米兰客场8战不败国米10年连胜'])
    print(f'predict_label: {predict_label}, predict_proba: {predict_proba}')
    del m

    new_m = TextClassifier('lr')
    new_m.load_model()
    predict_label, predict_label_prob = new_m.predict(['福建春季公务员考试报名18日截止 2月6日考试'])
    print(predict_label)
    print(predict_label_prob)  # [[0.53337174 0.46662826]]
    print('classes_: ', new_m.model.classes_)  # the classes ordered as prob
    print('sport prob: ', predict_label_prob[0][np.where(np.array(new_m.model.classes_) == 'sports')])

    test_data = [
        ('education', '福建春季公务员考试报名18日截止 2月6日考试'),
        ('sports', '意甲首轮补赛交战记录:米兰客场8战不败国米10年连胜'),
    ]
    acc_score = new_m.evaluate(test_data)
    print(acc_score)  # 1.0