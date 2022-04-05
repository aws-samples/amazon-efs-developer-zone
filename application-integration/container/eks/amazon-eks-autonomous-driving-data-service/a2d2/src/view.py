'''
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify,
merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
'''

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import numpy as np
import numpy.linalg as la

MIN_VECTOR_NORM = 1.0e-10

# Use Gram-Schmidt process  to find orthonormal  3-d vectors of view
def orthonormal_bases_of_view(view):
    x_axis = view['x-axis']
    y_axis = view['y-axis']
     
    x_axis_norm = la.norm(x_axis)
    y_axis_norm = la.norm(y_axis)
    
    if (x_axis_norm < MIN_VECTOR_NORM or y_axis_norm < MIN_VECTOR_NORM):
        raise ValueError("Norm of input vector(s) too small.")
        
    # normalize the axes
    x_axis = x_axis / x_axis_norm
    y_axis = y_axis / y_axis_norm
    
    # make a new y-axis which lies in the original x-y plane, but is orthogonal to x-axis
    y_axis = y_axis - x_axis * np.dot(y_axis, x_axis)
 
    # create orthogonal z-axis
    z_axis = np.cross(x_axis, y_axis)
    
    # calculate and check y-axis and z-axis norms
    y_axis_norm = la.norm(y_axis)
    z_axis_norm = la.norm(z_axis)
    
    if (y_axis_norm < MIN_VECTOR_NORM) or (z_axis_norm < MIN_VECTOR_NORM):
        raise ValueError("Norm of view axis vector(s) too small.")
        
    # make x/y/z-axes orthonormal
    y_axis = y_axis / y_axis_norm
    z_axis = z_axis / z_axis_norm
    
    return x_axis, y_axis, z_axis

# 3-d position vector of view origin
def origin_of_view(view):
    return view['origin']

# Compute a 4 x 4 matrix that transforms homegeneous view coordinates
# to homegeneous global coordinates
def transform_to_global(view):
    # get orthonormal axes of view
    x_axis, y_axis, z_axis = orthonormal_bases_of_view(view)
    
    # get origin of view
    origin = origin_of_view(view)
    transform_to_global_matrix = np.eye(4)
    
    # set rotation sub-matrix
    transform_to_global_matrix[0:3, 0] = x_axis
    transform_to_global_matrix[0:3, 1] = y_axis
    transform_to_global_matrix[0:3, 2] = z_axis
    
    # set translation vector
    transform_to_global_matrix[0:3, 3] = origin
    
    return transform_to_global_matrix

def transform_from_global(view):
   # transform to global matrix
   transform_to_global_matrix = transform_to_global(view)
   trans = np.eye(4)
   rot = np.transpose(transform_to_global_matrix[0:3, 0:3])
   trans[0:3, 0:3] = rot
   trans[0:3, 3] = np.matmul(rot, -transform_to_global_matrix[0:3, 3])
    
   return trans

def rot_to_global(view):
    # transform to global matrix
    transform_to_global_matrix = transform_to_global(view)
    # get rotation sub-matrix
    return transform_to_global_matrix[0:3, 0:3]
  
def rot_from_global(view):
    return np.transpose(rot_to_global(view))


def rot_from_to(src, target):
    return np.matmul(rot_from_global(target), rot_to_global(src))

def transform_from_to(src, target):
    return np.matmul(transform_from_global(target), transform_to_global(src))