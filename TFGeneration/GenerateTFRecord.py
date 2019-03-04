import tensorflow as tf
import numpy as np
import cv2
import os
import shutil
import pickle
from tqdm import tqdm
from multiprocessing import Process,Lock
import time

class GenerateTFRecord:
    def __init__(self, inpath, outpath,filesize):
        self.outtfpath = outpath
        self.inpath=inpath
        self.filesize=filesize
        self.writer=None
        if(not os.path.exists(self.outtfpath)):
            os.mkdir(self.outtfpath)

        if (not os.path.exists(self.inpath)):
            print('\nInput directory does not exist')

        self.inpicklepath = inpath
        self.num_of_max_vertices=900
        self.max_length_of_word=30
        self.num_data_dims=5
        self.fileslist=[]
        self.filecounter=1
        self.threadscounter=0
        self.lock=Lock()
        #self.str_to_chars=lambda str:np.chararray(list(str))

    def str_to_int(self,str):
        intsarr=np.array([ord(chr) for chr in str])
        padded_arr=np.zeros(shape=(self.max_length_of_word),dtype=np.int64)
        padded_arr[:len(intsarr)]=intsarr
        return padded_arr

    def convert_to_int(self, arr):
        return [int(val) for val in arr]

    def pad_with_zeros(self,arr,shape):
        dummy=np.zeros(shape,dtype=np.int64)
        dummy[:arr.shape[0],:arr.shape[1]]=arr
        return dummy

    def generate_tf_record(self, img_path, cellmatrix, rowmatrix, colmatrix, arr):


        cellmatrix=self.pad_with_zeros(cellmatrix,(self.num_of_max_vertices,self.num_of_max_vertices))
        colmatrix = self.pad_with_zeros(colmatrix, (self.num_of_max_vertices, self.num_of_max_vertices))
        rowmatrix = self.pad_with_zeros(rowmatrix, (self.num_of_max_vertices, self.num_of_max_vertices))

        im = np.array(cv2.imread(img_path, 0),dtype=np.int64)
        img_height, img_width=im.shape

        words_arr = arr[:, 1].tolist()
        no_of_words = len(words_arr)


        lengths_arr = self.convert_to_int(arr[:, 0])
        vertex_features=np.zeros(shape=(self.num_of_max_vertices,self.num_data_dims),dtype=np.int64)
        lengths_arr=np.array(lengths_arr).reshape(len(lengths_arr),-1)
        sample_out=np.concatenate((arr[:,2:],lengths_arr),axis=1)
        vertex_features[:no_of_words,:]=sample_out


        #vertex_text=np.chararray(shape=(self.num_of_max_vertices,self.max_length_of_word))
        #vertex_text[:no_of_words,:]=list(map(self.str_to_chars, words_arr))
        #vertex_text=words_arr+[""]*(self.num_of_max_vertices-len(words_arr))

        vertex_text = np.zeros((self.num_of_max_vertices,self.max_length_of_word), dtype=np.int64)
        vertex_text[:no_of_words]=np.array(list(map(self.str_to_int,words_arr)))


        feature = dict()
        feature['image'] = tf.train.Feature(float_list=tf.train.FloatList(value=im.astype(np.float32).flatten()))
        feature['global_features'] = tf.train.Feature(float_list=tf.train.FloatList(value=np.array([img_height, img_width,no_of_words]).astype(np.float32).flatten()))
        feature['vertex_features'] = tf.train.Feature(float_list=tf.train.FloatList(value=vertex_features.astype(np.float32).flatten()))
        feature['adjacency_matrix_cells'] = tf.train.Feature(int64_list=tf.train.Int64List(value=cellmatrix.astype(np.int64).flatten()))
        feature['adjacency_matrix_cols'] = tf.train.Feature(int64_list=tf.train.Int64List(value=colmatrix.astype(np.int64).flatten()))
        feature['adjacency_matrix_rows'] = tf.train.Feature(int64_list=tf.train.Int64List(value=rowmatrix.astype(np.int64).flatten()))
        feature['vertex_text'] = tf.train.Feature(int64_list=tf.train.Int64List(value=vertex_text.astype(np.int64).flatten()))

        all_features = tf.train.Features(feature=feature)


        seq_ex = tf.train.Example(features=all_features)
        return seq_ex

    def write_tf(self,input_files_paths,output_file_name):
        options = tf.python_io.TFRecordOptions(tf.python_io.TFRecordCompressionType.GZIP)

        with tf.python_io.TFRecordWriter(os.path.join(self.outtfpath,output_file_name),options=options) as writer:
            for i,img_path in enumerate(input_files_paths):
                pickle_file = open(img_path.replace('.png', ''), 'rb')
                arr = pickle.load(pickle_file)

                colmatrix = np.array(arr[1],dtype=np.int64)
                cellmatrix = np.array(arr[2],dtype=np.int64)
                rowmatrix = np.array(arr[0],dtype=np.int64)
                bboxes = np.array(arr[3])
                seq_ex = self.generate_tf_record(img_path, cellmatrix, rowmatrix, colmatrix, bboxes)
                writer.write(seq_ex.SerializeToString())

        print('\ncompleted:', output_file_name)

    def write_to_tf(self,max_threads):

        files_list=[]
        for directory in os.listdir(self.inpicklepath):
            dirpath=os.path.join(self.inpicklepath,directory)
            for file in os.listdir(dirpath):
                if (file.endswith('.png')):
                    files_list.append(os.path.join(dirpath, file))

        self.fileslist=files_list

        starttime=time.time()
        threads=[]
        start=0
        end=self.filesize

        self.fileslist=self.fileslist

        for end in range(self.filesize,len(self.fileslist),self.filesize):


            proc = Process(target=self.write_tf, args=(self.fileslist[start:end], str(self.filecounter) + '.tfrecord'))
            threads.append(proc)
            proc.start()
            start=end

            self.lock.acquire()
            self.threadscounter+=1
            self.filecounter+=1
            self.lock.release()


            if(self.threadscounter>=max_threads):
                for proc in threads:
                    proc.join()
                self.threadscounter=0

        end=len(self.fileslist)

        proc = Process(target=self.write_tf, args=(self.fileslist[start:end], str(self.filecounter) + '.tfrecord'))
        threads.append(proc)
        proc.start()
        proc.join()
        print(time.time()-starttime)

