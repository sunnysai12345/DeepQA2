# coding: utf8
# Copyright 2017 Hai Liang Wang. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============================================================================
import sys
import os
import logging
import configparser
import tensorflow as tf
from django.conf import settings
from django.apps import AppConfig
# import config
sys.path.append(os.path.join(os.path.dirname(
    os.path.realpath(__file__)), os.pardir, os.pardir))
from config import config
from dataset.textdata import TextData
from munch import munchify
from models.rnn import Model

logger = logging.getLogger(__name__)

class ChatbotManager(AppConfig):
    """ Manage a single instance of the chatbot shared over the website
    """
    name = 'api'
    td = None
    inited = False
    tf_model = None
    tf_session = None
    verbose_name = 'DeepQA2 RESt API'

    def ready(self):
        """ Called by Django only once during startup
        """
        # Initialize the chatbot daemon (should be launched only once)
        # HACK: Avoid initialisation while migrate
        if not any(x in sys.argv for x in ['makemigrations', 'migrate']):
            ChatbotManager.initBot()

    @staticmethod
    def initBot():
        """ Instantiate the chatbot for later use
        Should be called only once
        """
        if not ChatbotManager.inited:
            logger.info('Initializing bot ...')
                # load text data
            ChatbotManager.td = TextData(munchify({
                'rootDir': config.dataset_root_dir,
                'corpus': config.corpus_name,
                'maxLength': config.train_max_length,
                'maxLengthEnco': config.train_max_length_enco,
                'maxLengthDeco': config.train_max_length_deco,
                'datasetTag': '',
                'test': False,
                'watsonMode': False,
                'batchSize': config.train_num_batch_size
            }))
            
            # restore model
            with tf.device(None):
                ChatbotManager.tf_model = Model(config, config.dataset)
            tf_saver = tf.train.Saver(max_to_keep=200)
            ChatbotManager.tf_session = tf.Session()
            ChatbotManager.tf_session.run(tf.initialize_all_variables())
            logger.info('restore previous model ... %s' %
                        os.path.join(config.base_dir, 'model.ckpt'))
            tf_saver.restore(ChatbotManager.tf_session, os.path.join(config.base_dir, 'model.ckpt'))
            ChatbotManager.inited = True
        else:
            logger.info('Bot already initialized.')

    @staticmethod
    def callBot(sentence, questionSeq = None):
        """ Use the previously instantiated bot to predict a response to the given sentence
        Args:
            sentence (str): the question to answer
            questionSeq (List<int>): output argument. If given will contain the input batch sequence
        Return:
            list <int>: the word ids corresponding to the answer
        """
        logger.info('callBot %s' % sentence)
        if ChatbotManager.inited:
            batch = ChatbotManager.td.sentence2enco(sentence)
            logger.info('Get result from model2 ...')
            if not batch:
                return None
            if questionSeq is not None:  # If the caller want to have the real input
                questionSeq.extend(batch.encoderSeqs)
            # Run the model
            logger.info('Get result from model3 ...')
            ops, feedDict = ChatbotManager.tf_model.step(batch)
            # TODO: Summarize the output too (histogram, ...)
            output = ChatbotManager.tf_session.run(ops[0], feedDict)
            answer = ChatbotManager.td.deco2sentence(output)
            logger.info('answer<< %s' % answer)
            return answer
        else:
            logger.error('Error: Bot not initialized!')
