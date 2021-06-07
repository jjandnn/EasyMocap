'''
  @ Date: 2021-01-17 21:38:19
  @ Author: Qing Shuai
  @ LastEditors: Qing Shuai
  @ LastEditTime: 2021-06-04 15:52:49
  @ FilePath: /EasyMocap/easymocap/visualize/skelmodel.py
'''
import numpy as np
import cv2
from os.path import join
import os
from ..dataset.config import CONFIG

def calTransformation(v_i, v_j, r, adaptr=False, ratio=10):
    """ from to vertices to T
    
    Arguments:
        v_i {} -- [description]
        v_j {[type]} -- [description]
    """
    xaxis = np.array([1, 0, 0])
    v = (v_i + v_j)/2
    direc = (v_i - v_j)
    length = np.linalg.norm(direc)
    direc = direc/length
    rotdir = np.cross(xaxis, direc)
    rotdir = rotdir/np.linalg.norm(rotdir)
    rotdir = rotdir * np.arccos(np.dot(direc, xaxis))
    rotmat, _ = cv2.Rodrigues(rotdir)
    # set the minimal radius for the finger and face
    shrink = min(max(length/ratio, 0.005), 0.05)
    eigval = np.array([[length/2/r, 0, 0], [0, shrink, 0], [0, 0, shrink]])
    T = np.eye(4)
    T[:3,:3] = rotmat @ eigval @ rotmat.T
    T[:3, 3] = v
    return T, r, length

class SkelModel:
    def __init__(self, nJoints=None, kintree=None, body_type=None, joint_radius=0.02, **kwargs) -> None:
        if nJoints is not None:
            self.nJoints = nJoints
            self.kintree = kintree
        else:
            config = CONFIG[body_type]
            self.nJoints = config['nJoints']
            self.kintree = config['kintree']
        cur_dir = os.path.dirname(__file__)
        faces = np.loadtxt(join(cur_dir, 'sphere_faces_20.txt'), dtype=np.int)
        self.vertices = np.loadtxt(join(cur_dir, 'sphere_vertices_20.txt'))
        # compose faces
        faces_all = []
        for nj in range(self.nJoints):
            faces_all.append(faces + nj*self.vertices.shape[0])
        for nk in range(len(self.kintree)):
            faces_all.append(faces + self.nJoints*self.vertices.shape[0] + nk*self.vertices.shape[0])
        self.faces = np.vstack(faces_all)
        self.nVertices = self.vertices.shape[0] * self.nJoints + self.vertices.shape[0] * len(self.kintree)
        self.joint_radius = joint_radius

    def __call__(self, keypoints3d, id=0, return_verts=True, return_tensor=False, **kwargs):
        vertices_all = []
        r = self.joint_radius
        # joints 
        for nj in range(self.nJoints):
            if keypoints3d[nj, -1] < 0.01:
                vertices_all.append(self.vertices*0.001)
                continue
            vertices_all.append(self.vertices*r + keypoints3d[nj:nj+1, :3])
        # limb
        for nk, (i, j) in enumerate(self.kintree):
            if keypoints3d[i][-1] < 0.1 or keypoints3d[j][-1] < 0.1:
                vertices_all.append(self.vertices*0.001)
                continue
            T, _, length = calTransformation(keypoints3d[i, :3], keypoints3d[j, :3], r=1)
            if length > 2: # 超过两米的
                vertices_all.append(self.vertices*0.001)
                continue
            vertices = self.vertices @ T[:3, :3].T + T[:3, 3:].T
            vertices_all.append(vertices)
        vertices = np.vstack(vertices_all)
        return vertices[None, :, :]
    
    def init_params(self, nFrames):
        return np.zeros((self.nJoints, 4))

class SMPLSKEL:
    def __init__(self, model_type, gender, body_type) -> None:
        from ..smplmodel import load_model
        config = CONFIG[body_type]
        self.smpl_model = load_model(gender, model_type=model_type, skel_type=body_type)
        self.body_model = SkelModel(config['nJoints'], config['kintree'])

    def __call__(self, return_verts=True, **kwargs):
        keypoints3d = self.smpl_model(return_verts=False, return_tensor=False, **kwargs)
        if not return_verts:
            return keypoints3d
        else:
            verts = self.body_model(return_verts=True, return_tensor=False, keypoints3d=keypoints3d[0])
            return verts
    
    def init_params(self, nFrames):
        return np.zeros((self.body_model.nJoints, 4))