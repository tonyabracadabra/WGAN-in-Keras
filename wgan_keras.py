__author__ = "Xupeng Tong"
__copyright__ = "Copyright 2017, WGAN with Keras"
__email__ = "xtong@andrew.cmu.edu"

# Structure inspired by https://github.com/jiamings/wgan

import os
import time
import argparse
import importlib
import tensorflow as tf
import tensorflow.contrib as tc
from tqdm import tqdm
import keras
from keras.models import Sequential, Model
from keras.layers import Input
from keras import backend as K
import numpy as np

from visualize import *

class WassersteinGAN(object):
    def __init__(self, generator, discriminator, x_sampler, z_sampler, data, model):
        self.model = model
        self.data = data
        self.x_dim = discriminator.x_dim
        self.z_dim = generator.z_dim
        self.generator = generator()
        self.discriminator = discriminator()
        self.x_sampler = x_sampler
        self.z_sampler = z_sampler

        self.discriminator.compile(loss='categorical_crossentropy', optimizer='RMSprop')
        self.discriminator.summary()
        self.generator.compile(loss='binary_crossentropy', optimizer='RMSprop')
        self.discriminator.summary()

        X, y = self.get_train_pair(64, type='descriminator')
        d_loss = self.discriminator.train_on_batch(X, y)

        gan_input = Input(shape=[self.z_dim])
        H = self.generator(gan_input)
        gan_output = self.discriminator(H)

        self.gan = Model(gan_input, gan_output)
        self.gan.compile(loss='categorical_crossentropy', optimizer='RMSprop')
        self.gan.summary()

    def clip_d_weights(self):
        weights = [np.clip(w, -0.01, 0.01) for w in self.discriminator.get_weights()]
        self.discriminator.set_weights(weights)

    def get_train_pair(self, batch_size, type):
        if type == 'descriminator':
            x = self.x_sampler(batch_size)
            z = self.z_sampler(batch_size, self.z_dim)
            x_ = self.generator.predict(z)

            X = np.concatenate((x, x_))
            y = np.zeros([2 * batch_size, 2])

            y[0:batch_size, 1] = 1
            y[batch_size:, 0] = 1

        elif type == 'gan':
            X = self.z_sampler(batch_size, self.z_dim)
            y = np.zeros([batch_size, 2])
            y[:, 1] = 1

        return X, y

    def train(self, nb_epoch=5000, batch_size=64):
        start_time = time.time()
        for t in tqdm(range(nb_epoch)):
            d_iters = 5
            if t % 500 == 0 or t < 25:
                 d_iters = 100

            self.discriminator.trainable = True
            for _ in range(0, d_iters):
                self.clip_d_weights()
                X, y = self.get_train_pair(batch_size, type='descriminator')
                # print self.gan.input
                d_loss = self.discriminator.train_on_batch(X, y)

            # train Generator-Discriminator stack on input noise to non-generated output class
            X, y = self.get_train_pair(batch_size, type='gan')
            
            self.discriminator.trainable = False
            g_loss = self.gan.train_on_batch(X, y)

            if t % 100 == 0 or t < 100:
                # Train discriminator
                self.discriminator.trainable = True
                X, y = self.get_train_pair(batch_size, type='descriminator')
                d_loss = self.discriminator.train_on_batch(X, y)

                # Train Generator-Discriminator with descriminator fixed
                self.discriminator.trainable = False
                X, y = self.get_train_pair(batch_size, type='gan')
                g_loss = self.gan.train_on_batch(X, y)

                print('Iter [%8d] Time [%5.4f] d_loss [%.4f] g_loss [%.4f]' %
                        (t + 1, time.time() - start_time, d_loss - g_loss, g_loss))

            if t % 100 == 0:
                # Get noises for prediction
                z = self.z_sampler(batch_size, self.z_dim)
                # Predict the image generated by noises
                z_predict = self.generator.predict(z)
                # Converted to image
                img = self.x_sampler.data2img(z_predict)

                fig = plt.figure(self.data + '.' + self.model)
                grid_show(fig, img, x_sampler.shape)
                fig.savefig('logs/{}/{}.pdf'.format(self.data, t/100))
            
            # Updates plots
            # if e % plt_frq == plt_frq-1:
            #     plot_loss(losses)
            #     plot_gen()

if __name__ == '__main__':
    parser = argparse.ArgumentParser('')
    parser.add_argument('--data', type=str, default='mnist')
    parser.add_argument('--model', type=str, default='model_gan')
    parser.add_argument('--gpus', type=str, default='0')
    parser.add_argument('--batch_size', type=int, default=64)
    parser.add_argument('--nb_epoch', type=int, default=5000)

    args = parser.parse_args()

    data = importlib.import_module(args.data)
    model = importlib.import_module(args.data + '.' + args.model)

    x_sampler = data.DataSampler()
    z_sampler = data.NoiseSampler()

    discriminator = model.Discriminator()
    generator = model.Generator()

    wgan = WassersteinGAN(generator, discriminator, x_sampler, z_sampler, \
        args.data, args.model)

    wgan.train(nb_epoch=args.nb_epoch, batch_size=args.batch_size)
