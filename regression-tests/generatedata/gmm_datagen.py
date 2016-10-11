# vim: set encoding=utf-8

#  Copyright (c) 2016 Intel Corporation 
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

""" Generates data for gmm model
    params: n_samples: number of rows
            centers: number of centroids
            n_features: number of columns"""
from sklearn.datasets.samples_generator import make_blobs


def gen_data(n_rows, k, features):
    x,y = make_blobs(n_samples=n_rows, centers=k, n_features=features, random_state=14)
    for row in x.tolist():
        print ",".join(map(str,row))

gen_data(50, 5, 2)