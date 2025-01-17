# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: 
"""
import sys

sys.path.append('..')
from pytextclassifier.textcluster import TextCluster

if __name__ == '__main__':
    m = TextCluster(model_dir='models/cluster-toy', n_clusters=2)
    print(m)
    data = [
        'Student debt to cost Britain billions within decades',
        'Chinese education for TV experiment',
        'Abbott government spends $8 million on higher education',
        'Middle East and Asia boost investment in top level sports',
        'Summit Series look launches HBO Canada sports doc series: Mudhar'
    ]
    m.train(data)
    m.load_model()
    r = m.predict(['Abbott government spends $8 million on higher education media blitz',
                   'Middle East and Asia boost investment in top level sports'])
    print(r)

    ########### load chinese train data from 1w data file
    from sklearn.feature_extraction.text import TfidfVectorizer

    tcluster = TextCluster(model_dir='models/cluster', feature=TfidfVectorizer(ngram_range=(1, 2)), n_clusters=10)
    data = tcluster.load_file_data('thucnews_train_1w.txt', sep='\t', use_col=1)
    feature, labels = tcluster.train(data[:5000])
    tcluster.show_clusters(feature, labels, 'models/cluster/cluster_train_seg_samples.png')
    r = tcluster.predict(data[:30])
    print(r)
