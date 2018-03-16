#!/usr/bin/python3
from __future__ import division
__author__ = 'FoamWorkshop'

'''
program options:
-i [input files | all]
-a [float decimal accuracy] default 3
-narc [number o segments] - default 10
-larc [minimal segment length] - default 1
-cw   [1|0] default 1: 1 - clockwise; 0 - counter clockwise of the  closed path
-l process selected layers

info:
    the program extracts entities:
        LINE, ARC
    and converts them into a list of coordinates defining:
        1 - input/output path
        2 - closed contour paths

path finding alghoritm:
        1 - find a segment including the start knot (k0)
        2 - read the remining knot (r_k)
        3 - push (remove from the pool) the segment knots to the path list ordered like: [k0, r_k]
        4 - assign the new start knot as (k0) and repeat from 1 while the pool is not empty.
        5 - if the closed contour path, add the last segment connecting the first knot and the last in the path list [k(-1), k(0)]

program algorithm:
        1 - open dxf and go through all layers
        2 - find the entities and read DATA with specified accuracy:
             LINE - read START, END coordinates
             ARC - read START ANGLE, END ANGLE and RADIUS:
             convert the curve to segments with following options:
              n - number of segments
              or l_min - specified minimal segment length

            note: the concept is taken from Abaqus inp. files organisation
            the  output is:
             - list of segment coordinates [[x1,y1,y1], [x2,y2,y2];...]
             - list of segment knots [[x1,y1,y1]; [x2,y2,y2]; [xn, yn, zn];...]

        3 - remove duplicates from the segment knots list. position of a coordinate int the knot list indicates the knot number.
        4 - replace the segment list coordinates by knot numbers. the resultant list includes segment knot numbers [[k1, k2];[ki kn];...]
        5 - sort the segment list by knots count. the proper list should include 1 - io knot shared with a segment and: 1 - master knot shared between 3 segments
        6 - find the io_path with begin in io knot and end in master knot. the outcome is:
                io_path and remining segment pool for the closed path
        7 - find the END segment for clock wise or counter clock wise direction and exclude the last knot from the ranking list.
        8 - find the ct_path
        9 - save ct_path, io_path and reversed(io_path) to the output files

        improvements:
            #. fix dxf paths
            #. use regular expresion to match layer names
            #. layer naming convention
                number with a tag in '()':
                    xxxx()
                    xxxx.()
                    xxxx#y()
                    xxxx#y.()

            #. merging dxf drawings
                *layers with the same number before # are merged so:
                    xxxx#a('path with props 0')
                    xxxx#b('path with props 1')
                    xxxx#1('path with props 2')

            #. makeing drafting profiles
                *layers with the same number before # are merged so:
                    xxxx$0('path with props 0')
                    xxxx$1('path with props 1')

            #. drawing keywords:
                heating = 10(W)
                angle = 90(deg)
                radius = 100(mm)
                feed = 200(mm/min)
                start/circle center - indicates begining of an unlooped path

            #. data structure:
                r - radius
                a - angle
                z - axial
                s - slope
                c - cutting speed
                p - heating

        drawing options:
        continous lines
        loops
        import os
        '''

import argparse
import sys
import dxfgrabber
import numpy as np
import pickle
import cncfclib
import os
import re
import matplotlib.pyplot as plt

def ct_len_1(sect_arr):
    u = sect_arr[:,0,:]
    v = sect_arr[:,1,:]
    p = v - u
    l_arr = np.linalg.norm( p, axis=1)
    return np.sum(l_arr)

def main(args):

    dxf_list = args.input
    layer_list = args.layer
    dec_acc = args.accuracy
    n_arc = args.arc_seg_num
    l_arc = args.arc_seg_len
    path_dir = args.collection_dir
    eq_sect = args.equivalence_knots
    eq_sect_skip = args.skip_eq_sections
    z_coord = args.z_coord
    output_path = args.output_path

    files_dxf = dxf_list

    if 1:
        print('SETTINGS:')
        print('{0}{1:<30}: {2}'.format(' ' * 10, 'decimal accuracy', dec_acc))
        print('{0}{1:<30}: {2}'.format(' ' * 10, 'arc segments count', n_arc))
        print('{0}{1:<30}: {2}'.format(' ' * 10, 'minimal arc segment length', l_arc))
        print('{0}{1:<30}: {2}'.format(' ' * 10, 'equivalence sections', eq_sect))
        print('{0}{1:<30}: {2}'.format(' ' * 10, 'skip equivalence sections', eq_sect_skip))
        print('{0}{1:<30}: {2}'.format(' ' * 10, 'closed path collection dir', path_dir))
        print('{0}{1:<30}: {2}'.format(' ' * 10, 'files', files_dxf))
        print('{0}{1:<30}: {2}'.format(' ' * 10, 'layer name', layer_list[0]))
        print('{0}{1:<30}: {2}'.format(' ' * 10, 'output paths', output_path))
        print('{0}'.format('-' * 80))

        req_layer = layer_list[0]
        for i, files_dxf_member in enumerate(files_dxf):

            case_name = os.path.splitext(files_dxf_member)
            dxf = dxfgrabber.readfile(files_dxf_member, {"assure_3d_coords": True})
            dxf_layers = [var.name for var in dxf.layers]
            # print(dxf_layers)

            regex0 = re.compile("^({})(|[(])".format(req_layer), re.IGNORECASE)
            regex1 = re.compile("^({})[#].*".format(req_layer), re.IGNORECASE)
            regex2 = re.compile("^({})%.*".format(req_layer), re.IGNORECASE)

            z0 = [layer for layer in dxf_layers for m in [regex0.search(layer)] if m]
            z1 = [layer for layer in dxf_layers for m in [regex1.search(layer)] if m]
            z2 = [layer for layer in dxf_layers for m in [regex2.search(layer)] if m]

            dxf_params = (dec_acc, n_arc, l_arc)

            # if z0:
            #     print('single layer')
            #     io_path, lo_path, io_path_prop, lo_path_prop, prop_dict = cncfclib.extract_dxf_path(dxf,z0,dxf_params)
            #     cncfclib.plot_path([io_path, lo_path], [io_path_prop, lo_path_prop], [prop_dict])
            #
            # if z1:
            #     print('merge layers: ', z1)
            #     io_path, lo_path, io_path_prop, lo_path_prop, prop_dict = cncfclib.extract_dxf_path(dxf,z1,dxf_params)
            #     cncfclib.plot_path([io_path, lo_path], [io_path_prop, lo_path_prop],[prop_dict])

            if z2:
                regex3 = re.compile("^.*%.*#", re.IGNORECASE)

                z3 = sorted(list(set([m.group() for layer in z2 for m in [regex3.search(layer)] if m])))
                print(z3)
                regex31 = re.compile("^{}".format(z3[0]), re.IGNORECASE)
                regex32 = re.compile("^{}".format(z3[1]), re.IGNORECASE)
                z31 = [layer for layer in z2 for m in [regex31.search(layer)] if m]
                z32 = [layer for layer in z2 for m in [regex32.search(layer)] if m]

                io_path1, lo_path1, io_path_prop1, lo_path_prop1, prop_dict1 = cncfclib.extract_dxf_path(dxf, z31, dxf_params)
                io_path2, lo_path2, io_path_prop2, lo_path_prop2, prop_dict2 = cncfclib.extract_dxf_path(dxf, z32, dxf_params)

                cncfclib.plot_path([[io_path1, lo_path1],[io_path2, lo_path2]], [[io_path_prop1, lo_path_prop1], [io_path_prop2, lo_path_prop2]], [prop_dict1, prop_dict2])


                # struct_data1, prop_data1, prop_dict1, start_coord_arr1 = cncfclib.dxf_read_1(dxf, z2[0], dec_acc, n_arc, l_arc)
                # io_path1, io_rest1, io_path_prop1, io_rest_prop1 = cncfclib.find_io_path(struct_data1, prop_data1, start_coord_arr1)
                # pt01 = io_path1[-1,-1]
                # lo_path1, lo_rest1, lo_path_prop1, lo_rest_prop1 = cncfclib.find_lo_path(io_rest1, io_rest_prop1, pt01)
                #
                # struct_data2, prop_data2, prop_dict2, start_coord_arr2 = cncfclib.dxf_read_1(dxf, z2[1], dec_acc, n_arc, l_arc)




                # ax = plt.subplot(1,1,1)
                # for var in np.vstack((io_path,lo_path)):
                #     # print(var[:,0])
                #     plt.plot(var[:,0],var[:,1])
                # plt.grid(True)
                # plt.show()


            # for layer_name in sorted(layer_name_list):
#             for layer_name in sorted(z1):
#                 knots_list, elements_arr, segment_bounds, shape_count, start_coord, struct_data = cncfclib.dxf_read_1(dxf, layer_name, dec_acc, n_arc, l_arc)
#
#                 print('dxf loaded')
# #                 io_path, io_rest = cncfclib.find_io_path(elements_arr, start_coord)
#                 lo_path, lo_rest = cncfclib.find_lo_path(io_rest, io_path[-1,-1,:])
#
# #EQUIVALENCE SECTION
# #                 section_list = io_knots_coord
# #
# #                 if eq_sect:
# #                     print('drw. splits: {0:4d}'.format(segment_bounds.shape[0]))
# #                     section_list = []
# #                     section = []
# #                     updated_section_list = []
# #                     n_seg = np.linspace(0,1,eq_sect)
# #                     # print(segment_bounds)
# #                     for i, var in enumerate(io_knots_coord):
# #                         section.append(var)
# #                         # print(var)
# #                         if var in segment_bounds:
# #                             # print(var)
# #                             section_list.append(section)
# #                             section = []
# #                             section.append(var)
# #                     section_list.append(section)
# #
# #                     for i, section in enumerate(section_list):
# #                         if i not in eq_sect_skip and i not in [var+len(segment_bounds) for var in eq_sect_skip]:
# #                             # print('equivalence section {}'.format(i))
# #                             p = np.array(section)
# #                             l = np.sqrt(np.diff(p[:,0])**2 + np.diff(p[:,1])**2)
# #                             l = np.cumsum(np.hstack((0,l)))
# #                             # print(n_seg)
# #                             # print(l)
# #                             l_norm = l/l[-1]
# #                             # print(l_norm)
# #                             x=np.interp(n_seg, l_norm, p[:,0])
# #                             y=np.interp(n_seg, l_norm, p[:,1])
# #                             z=np.vstack((x,y)).T
# #                             # print(z)
# #                             section = z.tofileslist()
# #                         updated_section_list.append(section)
# # #flatten the list of lists
# #                     section_list = [var for sublist in updated_section_list for var in sublist]
#
#
#
# #SUMMARY
#                 speed = 60/200
#                 print('{0:11}: {1:4d} | cut len: {2:4.0f} | cut time {3:4.0f}s'.format('i/o  seg.', io_path.shape[0], ct_len_1(io_path), ct_len_1(io_path)*speed))
#                 print('{0:11}: {1:4d} | cut len: {2:4.0f} | cut time {3:4.0f}s'.format('loop seg.', lo_path.shape[0], ct_len_1(lo_path), ct_len_1(lo_path)*speed))
#                 print('{0}'.format('-' * 80))
# #SUMMARY
#                 if '1' in output_path:
#                     i_file_name = '{1}{2}.{3}'.format(case_name[0], layer_name, '1', 'knt')
#                     np.save(i_file_name, io_path)
#
#                 if '3' in output_path:
#                     o_file_name = '{1}{2}.{3}'.format(case_name[0], layer_name, '3', 'knt')
#                     np.save(o_file_name, io_path[::-1])
#
#                 if '2' in output_path:
#                     ct_file_name = '{1}{2}.{3}'.format(case_name[0], layer_name, '2', 'knt')
#                     # knots2file(ct_file_name, ct_path, sorted_knots)
#                     # size = len(section_list)+1
#                     # a_arr=np.zeros((1,size,1))
#                     # r_arr=np.zeros((1,size,1))
#                     # z_arr=np.zeros((1,size,1))
#                     # v_arr=np.zeros((1,size,2))
#                     #
#                     # print('found: ', len(section_list)+1,' shape sections')
#                     # for i, var in enumerate(ct_path):
#                     #     coord = knot2coord(sorted_knots, var[0])
#                     #     # print(coord)
#                     #     a_arr[0,i,0] = 0
#                     #     r_arr[0,i,0] = coord[0]
#                     #     z_arr[0,i,0] = coord[1]
#                     #     v_arr[0,i,:] = np.array([1,0])
#                     #
#                     # a_arr[0,-1,0]=a_arr[0,0,0]
#                     # r_arr[0,-1,0]=r_arr[0,0,0]
#                     # z_arr[0,-1,0]=0
#                     # v_arr[0,-1,:]=v_arr[0,0,:]
#                     #
#                     # res_dict = {'a_arr':np.rot90(a_arr, k=-1), #rotation angle
#                     #             'r_arr':np.rot90(r_arr, k=-1), #radius R/X
#                     #             'z_arr':np.rot90(z_arr, k=-1), #height Z/Y
#                     #             'v_arr':np.rot90(v_arr, k=-1)} #slope (useful for tapered wings)
#                     #
#                     # with open(ct_file_name, 'wb') as f:
#                     # # Pickle the 'data' dictionary using the highest protocol available.
#                     #     pickle.dump(res_dict, f, pickle.HIGHEST_PROTOCOL)

                # print(' saved')

if __name__ == '__main__':
    #*********************************************************************DEFAULT PARAMETERS
    dflt_dxf_list = 'all'
    dflt_dec_acc = 4  # decimal accuracy
    dflt_n_arc = 10  # number of segments
    dflt_l_arc = 0.1  # minimal segment length
    dflt_path_dir = 1  # closed path collecting direction
    #*********************************************************************PROGRAM

    parser = argparse.ArgumentParser(description='test')
    parser.add_argument('-i', '--input', nargs='+', help='input filenames')
    parser.add_argument('-l', '--layer', nargs='+', help='input layers')
    parser.add_argument('-a', '--accuracy', type=int,
                        default=dflt_dec_acc, help='decimal accuracy, default: 3')
    parser.add_argument('-narc', '--arc_seg_num', type=int,
                        default=dflt_n_arc, help='arc segments number, default: 10')
    parser.add_argument('-larc', '--arc_seg_len', type=float,
                        default=dflt_l_arc, help='minimal arc segment length, default: 0.1')
    parser.add_argument('-cw', '--collection_dir', type=int,
                        default=dflt_path_dir, help='closed path collection dir')
    parser.add_argument('-eq', '--equivalence_knots', type=int,
                        default=False, help='equivalence knots sections to specified number')
    parser.add_argument('-eq_skip', '--skip_eq_sections', nargs='+', type=int,
                        default=[], help='equivalence knots sections to specified number')
    parser.add_argument('-z', '--z_coord', type=float,
                        default=0, help='add z coordinate to knots')
    parser.add_argument('-op', '--output_path', type=str,
                        default='123', help='output path request')

    parser.add_argument('-plt', '--plot_paths', action='store_true', help='plot cutting paths')

    args = parser.parse_args()

    main(args)
