#! /usr/bin/env python
#-*- coding:utf-8 -*-

from utils import *
from segment import Segmenter
from vocab import *
from cnt_words import get_pop_quatrains
from rank_words import get_word_ranks
from utils import embed_w2v
from word2vec import get_word_embedding
import numpy as np
import shutil
import random


train_path = os.path.join(data_dir, 'train.txt')
kw_train_path = os.path.join(data_dir, 'kw_train.txt')


def fill_np_matrix(vects, batch_size, dummy):
    max_len = max(len(vect) for vect in vects)
    res = np.full([batch_size, max_len], dummy, dtype = np.int32)
    for row, vect in enumerate(vects):
        res[row, :len(vect)] = vect
    return res


def fill_np_array(vect, batch_size, dummy):
    res = np.full([batch_size], dummy, dtype = np.int32)
    res[:len(vect)] = vect
    return res


def _gen_train_data():
    segmenter = Segmenter()
    poems = get_pop_quatrains()
    random.shuffle(poems)
    ranks = get_word_ranks()
    print "Generating training data ..."
    data = []
    kw_data = []
    for idx, poem in enumerate(poems):
        sentences = poem['sentences']
        if len(sentences) == 4:
            flag = True
            lines = u''
            rows = []
            kw_row = []
            for sentence in sentences:
                rows.append([sentence])
                segs = filter(lambda seg: seg in ranks, segmenter.segment(sentence))
                if 0 == len(segs):
                    flag = False
                    break
                keyword = reduce(lambda x,y: x if ranks[x] < ranks[y] else y, segs)
                kw_row.append(keyword)
                rows[-1].append(keyword)
            if flag:
                data.extend(rows)
                kw_data.append(kw_row)
        if 0 == (idx+1)%2000:
            print "[Training Data] %d/%d poems are processed." %(idx+1, len(poems))
    with codecs.open(train_path, 'w', 'utf-8') as fout:
        for row in data:
            fout.write('\t'.join(row)+'\n')
    with codecs.open(kw_train_path, 'w', 'utf-8') as fout:
        for kw_row in kw_data:
            fout.write('\t'.join(kw_row)+'\n')
    print "Training data is generated."


def get_train_data():
    if not os.path.exists(train_path):
        _gen_train_data()
    data = []
    with codecs.open(train_path, 'r', 'utf-8') as fin:
        line = fin.readline()
        while line:
            toks = line.strip().split('\t')
            data.append({'sentence':toks[0], 'keyword':toks[1]})
            line = fin.readline()
    return data

def get_keras_train_data():
    train_data = get_train_data()
    _, ch2int = get_vocab()
    
    X_train = []
    Y_train = []
    for idx in xrange(len(train_data)):
        line_number = idx % 4
        
        keyword = train_data[idx]['keyword']
        current_sentence = train_data[idx]['sentence']
        previous_sentences = ''.join([train_data[idx - i]['sentence'] for i in range(line_number, 0, -1)])
        
        X_entry = pad_to([ch2int[ch] for ch in (keyword + previous_sentences)], 26, 5999)
        Y_entry = pad_to([ch2int[ch] for ch in current_sentence], 8, 5999)
        
        X_train.append(X_entry)
        Y_train.append(Y_entry)
        
    return X_train, Y_train

def gen_keras_one_hot_train_data(batch_size=64):
    print 'Preparing data'
    embedding = get_word_embedding(128)
    X_train, Y_train = get_keras_train_data()

    X_train_embedded = embed_w2v(embedding, X_train)
    Y_train_one_hot = apply_one_hot(Y_train)

    n_samples = len(X_train)


    print 'Data preparation completed'
    i = 0 
    while True:

        yield np.array(X_train_embedded[i: i + batch_size]), np.array(Y_train_embedded[i: i + batch_size])

        if i + batch_size > n_samples:
            i = 0
        else:
            i += batch_size


def gen_keras_train_data(batch_size=64):
    print 'Preparing data'
    embedding = get_word_embedding(128)
    X_train, Y_train = get_keras_train_data()

    X_train_embedded = embed_w2v(embedding, X_train)
    Y_train_embedded = embed_w2v(embedding, Y_train)

    n_samples = len(X_train)


    print 'Data preparation completed'
    i = 0 
    while True:

        yield np.array(X_train_embedded[i: i + batch_size]), np.array(Y_train_embedded[i: i + batch_size])

        if i + batch_size > n_samples:
            i = 0
        else:
            i += batch_size


def get_kw_train_data():
    if not os.path.exists(kw_train_path):
        _gen_train_data()
    data = []
    with codecs.open(kw_train_path, 'r', 'utf-8') as fin:
        line = fin.readline()
        while line:
            data.append(line.strip().split('\t'))
            line = fin.readline()
    return data


def batch_train_data(batch_size):
    if not os.path.exists(train_path):
        _gen_train_data()
    _, ch2int = get_vocab()
    with codecs.open(train_path, 'r', 'utf-8') as fin:
        stop = False
        while not stop:
            batch_s = [[] for _ in range(4)]
            batch_kw = [[] for _ in range(4)]
            for i in range(batch_size):
                line = fin.readline()
                if not line:
                    stop = True
                    break
                else:
                    toks = line.strip().split('\t')
                    batch_s[i%4].append([0]+[ch2int[ch] for ch in toks[0]]+[VOCAB_SIZE-1])
                    batch_kw[i%4].append([ch2int[ch] for ch in toks[1]])
            if 0 == len(batch_s[0]):
                break
            else:
                kw_mats = [fill_np_matrix(batch_kw[i], batch_size, VOCAB_SIZE-1) \
                        for i in range(4)]
                kw_lens = [fill_np_array(map(len, batch_kw[i]), batch_size, 0) \
                        for i in range(4)]
                s_mats = [fill_np_matrix(batch_s[i], batch_size, VOCAB_SIZE-1) \
                        for i in range(4)]
                s_lens = [fill_np_array([len(x)-1 for x in batch_s[i]], batch_size, 0) \
                        for i in range(4)]
                yield kw_mats, kw_lens, s_mats, s_lens


if __name__ == '__main__':
    train_data = get_train_data()
    print "Size of the training data: %d" %len(train_data)
    kw_train_data = get_kw_train_data()
    print "Size of the keyword training data: %d" %len(kw_train_data)
    assert len(train_data) == 4*len(kw_train_data)

