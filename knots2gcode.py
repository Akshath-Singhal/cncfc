#!/usr/bin/python

__author__ = 'FoamWorkshop'

'''The program automaticaly extracts cutting path from a dxf file.
The cutting path is split into:
1. IO_path - in/out path begining with single knot
2. ct_path - closed loop, begin and end in master knot position
the output of the program is a set of files with an ordered list of knots'''

import dxfgrabber
import numpy as np
import argparse
import pickle
import cncfclib as cf

def sub_points(p1, p2):
    vect = []
    p1 = [x for x in p1[0]]
    p2 = [x for x in p2[0]]
 #   print p3, p4
    print( len(p1))
    print( len(p2))
    if len(p1) == len(p2):
        for i, n in enumerate(p2):
            vect.append(n - p1[i])
        return vect
    return len(p1) * [None]

def p_l_intersection(p0,vec_n,l0,l1):
    vec_l=np.subtract(l1,l0)
    param1=np.subtract(p0,l0)
    d=(np.dot(param1,vec_n))/(np.dot(vec_l,vec_n))
    vec_l=np.multiply(d,vec_l)
    return np.add(vec_l,l0)

def p_l_intersection_series(p0,vec_n,data1,data2):
    if len(data1)==len(data2):
        print( "data ok")
        tmp=[]
        for i in range(len(data1)):
            l0=data1[i]
            l1=data2[i]
            tmp.append(p_l_intersection(p0,vec_n,l0,l1))
        return tmp
    else:
        return [0,0,0]

def gcodexyuv(dataxy, datauv):

    if len(dataxy)==len(datauv):
        print( "data ok")
        tmp=[]
        for i in range(len(dataxy)):
            tmp.append('g1 x{0:6.3f} y{1:6.3f} u{2:6.3f} v{3:6.3f}'.format(dataxy[i][0], dataxy[i][1], datauv[i][0], datauv[i][1]))

        fgcode=open('test.ngc','w')
        for line in tmp:
            fgcode.write(line)
            fgcode.write('\n')
        fgcode.close()
        return tmp

    else:
        print( "nie mozna wygenerowac g codu. rozne dlugosci sciezek.")
        return 0

#*********************************************************************DEFAULT PARAMETERS
dflt_dxf_list = 'all'  # decimal accuracy
dflt_dec_acc = 3  # decimal accuracy
dflt_n_arc = 10  # number of segments
dflt_l_arc = 1  # minimal segment length
dflt_path_dir = 1  # closed path collecting direction
d=421
d_rat = 0.5
symm_pref = 's'
#*********************************************************************PROGRAM
knt_data = []
knt_list_r = []
knt_data_r = []

parser = argparse.ArgumentParser(description='test')
parser.add_argument('-i',  '--input', nargs='+',type=str, help='xy uv input filenames')
parser.add_argument('-ir', '--input_r', nargs='+',type=str, help='R input filename')
parser.add_argument('-o', '--output', type=str, help='input filenames')
parser.add_argument('-sh', '--subset_header', action='store_true')
parser.add_argument('-gh', '--global_header', action='store_true')
parser.add_argument('-sw', '--swing_cut', action='store_true')
parser.add_argument('-cm', '--center_model', action='store_true')
parser.add_argument('-d', '--distance', type=float, default=d, help='distance between columns')
parser.add_argument('-dr', '--distance_ratio', type=float, default=d_rat, help='(xy-C)/d')
parser.add_argument('-symm', '--symmetry', action='store_true')

args = parser.parse_args()

knt_list = args.input
knt_list_r = args.input_r

subset_header = args.subset_header
global_header = args.global_header
center_model = args.center_model
output_f_name = args.output
symm_stat = args.symmetry
sw = args.swing_cut
d = args.distance
d_rat = args.distance_ratio

if '.knt' in knt_list:
    if knt_list_r:
        knt_set_r = knt_list_r[0]
        knt_data_r = read_data(knt_set_r, False)

    if len(knt_list)==1:
        knt_set_xy = knt_list[0]
        knt_set_uv = knt_list[0]

    elif len(knt_list)>=2:
        knt_set_xy = knt_list[0]
        knt_set_uv = knt_list[1]
        print('1xy:',knt_set_xy)
        print('1uv:',knt_set_uv)

    if not output_f_name:
        output_f_name='_'.join([knt_set_xy.replace('.knt',''),knt_set_uv.replace('.knt','')])

        knt_data_xy = read_data(knt_set_xy, False)
        knt_data_uv = read_data(knt_set_uv, False)

if '.pickle' in knt_list[0]:
    with open(knt_list[0], 'rb') as f:
        knt_dict = pickle.load(f)
        print('loaded pickle')

    # print(knt_dict.keys())
    a_arr=knt_dict['a_arr']
    r_arr=knt_dict['r_arr']
    z_arr=knt_dict['z_arr']
    v_arr=knt_dict['v_arr']
    # print(z_arr)

    if sw:
        print('modifed for swing cutting')
        a_arr[1::2,:] = a_arr[1::2,::-1]
        r_arr[1::2,:] = r_arr[1::2,::-1]
        z_arr[1::2,:] = z_arr[1::2,::-1]
        v_arr[1::2,:,:] = v_arr[1::2,::-1,:]

    prefix=''
    suffix=''
    gc_model=[]

    # print(z_arr)
    for i, (x, y, b) in enumerate(zip(r_arr, z_arr, a_arr)):
        gc_model.append('(---cut {0}---)\n'.format(i))
        gc_model.append(prefix)
        gc_model.append(cf.coords2gcode(x,y,x,y,b))
        gc_model.append(suffix)
    # print(gc_model)
    cf.savegcode(gc_model, name='fuselage', subset_header=True)
    print('saved gcode')



    # knt_data_xy = read_data(knt_set_xy, False)
    # knt_data_uv = read_data(knt_set_uv, False)




# if len(knt_data_xy)!=len(knt_data_uv):
#     print('knots: {0} - {1} are not balanced ({2} - {3}). EXIT'.format(knt_set_xy, knt_set_uv, len(knt_data_xy), len(knt_data_uv)))
# else:
#     print('processing knots: {0} - {1}'.format(knt_set_xy, knt_set_uv))
#
#     pool=zip(knt_data_xy, knt_data_uv)
#     knt_data_xy=[[varxy[0], varxy[1], varxy[2]+int(not(varxy[2]-varuv[2]))] for varxy, varuv in pool]
#     knt_data_uv=[[varuv[0], varuv[1], varuv[2]-int(not(varxy[2]-varuv[2]))] for varxy, varuv in pool]
#
#     pool=[]
#     if center_model:
#         # for varxy, varuv in zip(knt_data_xy, knt_data_uv):
#         pool=zip(knt_data_xy, knt_data_uv)
#         knt_data_xy=[[varxy[0], varxy[1], varxy[2]-0.5*(varxy[2]+varuv[2])] for varxy, varuv in pool]
#         knt_data_uv=[[varuv[0], varuv[1], varuv[2]-0.5*(varxy[2]+varuv[2])] for varxy, varuv in pool]
#
#     mashpathxy=p_l_intersection_series([0,0,d *  d_rat   ],[0,0,1],knt_data_xy,knt_data_uv)
#     mashpathuv=p_l_intersection_series([0,0,d * (d_rat-1)],[0,0,1],knt_data_uv,knt_data_xy)
#
#     write_data('{0}_{1}.knt'.format('xy',output_f_name),mashpathxy,True)
#     write_data('{0}_{1}.knt'.format('uv',output_f_name),mashpathuv,True)
#
#     knots2gcode(mashpathxy, mashpathuv,knt_data_r, output_f_name, global_header, subset_header)
#
#     if symm_stat:
#         knots2gcode(mashpathuv, mashpathxy,knt_data_r, ''.join([symm_pref, output_f_name]), global_header, subset_header)
