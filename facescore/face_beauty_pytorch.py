"""
face beauty prediction implemented by PyTorch
"""
import os
import sys

import cv2
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torchvision.transforms as transforms
from torch.autograd import Variable
from torch.utils.data import Dataset, DataLoader

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
from facescore.config import *


class FBNet(nn.Module):
    """network definition"""

    def __init__(self):
        super(FBNet, self).__init__()
        # 1 input image channel, 6 output channels, 5x5 square convolution
        # kernel
        self.conv1 = nn.Conv2d(3, 32, 5)
        self.conv2 = nn.Conv2d(32, 64, 5)
        self.conv3 = nn.Conv2d(64, 128, 3)
        # an affine operation: y = Wx + b
        self.fc1 = nn.Linear(128 * 5 * 5, 120)
        self.fc2 = nn.Linear(120, 64)
        self.fc3 = nn.Linear(64, 1)

    def forward(self, x):
        # Max pooling over a (2, 2) window
        x = F.max_pool2d(F.relu(self.conv1(x)), (2, 2))
        # If the size is a square you can only specify a single number
        x = F.max_pool2d(F.relu(self.conv2(x)), 2)
        x = F.max_pool2d(F.relu(self.conv3(x), 2))
        x = x.view(-1, self.num_flat_features(x))
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = self.fc3(x)

        return x

    def num_flat_features(self, x):
        size = x.size()[1:]  # all dimensions except the batch dimension
        num_features = 1
        for s in size:
            num_features *= s
        return num_features


class FaceBeautyDataset(Dataset):
    """Face Beauty Dataset"""

    def __init__(self, train=True, transform=None):
        """
        Args:
            csv_file (string): Path to the csv file with annotations.
            root_dir (string): Directory with all the images.
            transform (callable, optional): Optional transform to be applied
                on a sample.
        """
        self.face_images = np.array([config['face_image_filename'].format(_) for _ in
                                     pd.read_excel(config['label_excel_path'], 'Sheet1')['Image'].tolist()])
        self.beauty_labels = pd.read_excel(config['label_excel_path'], 'Sheet1')['Attractiveness label']
        self.transform = transform

    def __len__(self):
        return len(self.face_images)

    def __getitem__(self, idx):
        img_name = self.face_images[idx]
        image = cv2.imread(img_name)
        face_score = self.beauty_labels[idx]

        sample = {'image': image - np.mean(image), 'score': face_score}

        if self.transform:
            sample = self.transform(sample)

        return sample


def split_data(test_ratio):
    """
    split dataset into train set and test set
    :return:
    """
    df = pd.read_excel(config['label_excel_path'], 'Sheet1')
    filename_indexs = df['Image']
    attractiveness_scores = df['Attractiveness label']

    shuffled_indices = np.random.permutation(len(df))
    test_set_size = int(len(df) * test_ratio)
    test_indices = shuffled_indices[:test_set_size]
    train_indices = shuffled_indices[test_set_size:]

    return filename_indexs.iloc[train_indices], attractiveness_scores.iloc[train_indices], \
           filename_indexs.iloc[test_indices], attractiveness_scores.iloc[test_indices]


def train():
    transform = transforms.Compose(
        [transforms.RandomCrop(config['image_size']),
         transforms.ToTensor(),
         transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))])
    transformed_dataset = FaceBeautyDataset(transform=transform)
    dataloader = DataLoader(transformed_dataset, batch_size=config['batch_size'],
                            shuffle=True, num_workers=4)

    net = FBNet()
    if torch.cuda.is_available():
        net = net.cuda()

    criterion = nn.MSELoss()
    optimizer = optim.SGD(net.parameters(), lr=1e-4, momentum=0.9)

    for epoch in range(200):  # loop over the dataset multiple times

        running_loss = 0.0
        for i_batch, sample_batched in enumerate(dataloader):
            inputs, labels = sample_batched
            if torch.cuda.is_available():
                inputs = Variable(inputs.cuda())
                labels = Variable(labels.cuda())
            else:
                inputs, labels = Variable(inputs), Variable(labels)

            optim.zero_grad()
            outputs = net.forward(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            # print statistics
            running_loss += loss.data[0]
            if i_batch % 2000 == 1999:
                print('[%d, %5d] loss: %.3f' %
                      (epoch + 1, i_batch + 1, running_loss / 2000))
                running_loss = 0.0

    print('Finished Training')


if __name__ == '__main__':
    train()
