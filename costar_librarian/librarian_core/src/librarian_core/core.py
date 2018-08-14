#!/usr/bin/env python
import rospy
import os
import roslib
import rosparam
import StringIO
import tarfile
import time
from librarian_msgs.msg import *
from librarian_msgs.srv import *
from os.path import expanduser
from os.path import join
from ready_debug_tools.profile_helpers import ScopedProfile
roslib.load_manifest("rosparam")


class Librarian(object):
    """
    Librarian()
    Class containing functions to save and write configuration information to files.
    Files are grouped by "types" like Volumes, Robots, Objects, etc.
    These are all saved into different folders in a root directory.
    """

    '''
    __init__()
    Loads in the appropriate root parameter for the library of items.
    Advertises services, and loads some information about different items.
    '''
    def __init__(self, start_srvs=True):
        root = rospy.get_param('~librarian_root', '~/.costar/')
        self._root = expanduser(root)
        print "Librarian working directory: {}".format(self._root)

        self._records = {}

        if start_srvs is True:
            self._save_srv = rospy.Service('librarian/save', Save, self.save)
            self._load_srv = rospy.Service('librarian/load', Load, self.load)
            self._list_srv = rospy.Service('librarian/list', List, self.get_list)
            self._load_param_srv = rospy.Service('librarian/load_params', LoadParams, self.load_params)
            self._add_type_srv = rospy.Service('librarian/add_type', AddType, self.add_type)
            self._get_path_srv = rospy.Service('librarian/get_path', GetPath, self.create_path)
            self._get_path_to_type_srv = rospy.Service('librarian/get_path_to_type', GetTypePath, self.create_type_path)
            self._delete_srv = rospy.Service('librarian/delete', Delete, self.delete)
            self._save_tarball_service = rospy.Service('/librarian/save_tarball', SaveTarball, self.save_tarball)
            self._list_tarball_service = rospy.Service('/librarian/list_tarball', ListTarball, self.list_tarball)
            self._load_tarball_service = rospy.Service('/librarian/load_tarball', LoadTarball, self.load_tarball)

        self.init()
        self.load_records()

    def _get_type_root(self, requested_type):
        """
            requested_type (str): The costar subdirectory used to append onto the root.

            Returns:
                str: The absolute path to the requested_type's directory
        """
        return join(self._root, requested_type)

    def _get_tar_filename(self, requested_type, id):
        return join(self._get_type_root(requested_type), id) + '.tar'

    '''
    create_path()
    Create a path
    '''
    def create_path(self, req):
        resp = GetPathResponse()
        if len(req.type) == 0:
                resp.status.result = Status.FAILURE
                resp.status.error = Status.TYPE_MISSING
                resp.status.info = "No type provided!"
        else:
            path = join(self._root, req.type)
            filename = join(path, req.id)

            if not os.path.exists(path):
                resp.status.result = Status.FAILURE
                resp.status.error = Status.NO_SUCH_TYPE
                resp.status.info = "Type {} does not exist!".format(req.type)
            else:
                resp.path = filename

        return resp
    '''
    create_path()
    Create a path
    '''
    def create_type_path(self, req):
        resp = GetTypePathResponse()
        if len(req.type) == 0:
                resp.status.result = Status.FAILURE
                resp.status.error = Status.TYPE_MISSING
                resp.status.info = "No type provided!"
        else:
            filename = join(self._root, req.type)

            if not os.path.exists(filename):
                resp.status.result = Status.FAILURE
                resp.status.error = Status.NO_SUCH_TYPE
                resp.status.info = "Type {} does not exist!".format(req.type)
            else:
                resp.path = filename

        return resp

    '''
    init()
    If the library directory specified does not exist, set one up.
    '''
    def init(self):
        if not os.path.exists(self._root):
            os.mkdir(self._root)

    '''
    delete()
    Remove an item tracked by librarian.
    '''
    def delete(self, req):
        resp = DeleteResponse()

        if len(req.type) == 0:
            resp.status.result = Status.FAILURE
            resp.status.error = Status.TYPE_MISSING
            resp.status.info = "No type provided!"
        else:
            path = join(self._root, req.type)
            filename = join(path, req.id)

            if not os.path.exists(path):
                resp.status.result = Status.FAILURE
                resp.status.error = Status.NO_SUCH_TYPE
                resp.status.info = "Type {} does not exist!".format(req.type)
            else:
                os.remove(filename)
                resp.status.result = Status.SUCCESS

        return resp

    '''
    save()
    Save text to a file.
    '''
    def save(self, req):
        resp = SaveResponse()
        if len(req.type) == 0:
                resp.status.result = Status.FAILURE
                resp.status.error = Status.TYPE_MISSING
                resp.status.info = "No type provided!"
        else:
            path = join(self._root, req.type)
            filename = join(path, req.id)

            if not os.path.exists(path):
                resp.status.result = Status.FAILURE
                resp.status.error = Status.NO_SUCH_TYPE
                resp.status.info = "Type {} does not exist!".format(req.type)
            else:

                # get the operation
                if req.operation == SaveRequest.APPEND:
                    op = 'a'
                else:
                    op = 'w'

                # save the file
                out = open(filename, op)
                out.write(req.text)
                out.close()

                resp.status.result = Status.SUCCESS

        return resp


    '''
    save_tarball()
    Save a list of files to a single archive
    '''
    def save_tarball(self, req):
        with ScopedProfile('save_tarball'):
            filename = self._get_tar_filename(req.type, req.id)
            tar = tarfile.open(filename, 'w')
            for index, name in enumerate(req.filenames):
                string_buffer = StringIO.StringIO(req.filedata[index])
                tar_info = tarfile.TarInfo(name=name)
                tar_info.size = string_buffer.len
                tar_info.mtime = time.time()
                tar.addfile(tar_info, fileobj=string_buffer)

            tar.close()
        resp = SaveTarballResponse()
        resp.status.result = Status.SUCCESS
        return resp

    '''
    list_tarball()
    Return a list of filenames contained within the tarball
    '''
    def list_tarball(self, req):
        names = list()
        with ScopedProfile('list_tarball'):
            filename = self._get_tar_filename(req.type, req.id)
            if not os.path.exists(filename):
                resp = ListTarballResponse()
                resp.status.result = Status.FAILURE
                resp.status.error = Status.TYPE_MISSING
                return resp

            with tarfile.open(filename, 'r') as tar:
                names = tar.getnames()

        resp = ListTarballResponse()
        resp.status.result = Status.SUCCESS
        resp.entries = names
        return resp

    '''
    load_tarball()
    Open and read a single file from the tarball
    '''
    def load_tarball(self, req):
        text = None
        with ScopedProfile('load_tarball'):
            filename = self._get_tar_filename(req.type, req.id)
            if not os.path.exists(filename):
                resp = LoadTarballResponse()
                resp.status.result = Status.FAILURE
                resp.status.error = Status.TYPE_MISSING
                return resp


            with tarfile.open(filename, 'r') as tar:
                tar_info = tar.getmember(req.requested_filename)
                file_object = tar.extractfile(tar_info)
                text = file_object.read()

        resp = LoadTarballResponse()
        resp.status.result = Status.SUCCESS
        resp.text = text
        return resp

    '''
    add_type()
    Add a type of object to store in the Librarian workspace.
    '''
    def add_type(self, req):
        resp = AddTypeResponse()
        if len(req.type) == 0:
                resp.status.result = Status.FAILURE
                resp.status.error = Status.TYPE_MISSING
                resp.status.info = "No type provided!"
        else:
            path = join(self._root, req.type)

            # create a directory for objects of this type if necessary
            if not os.path.exists(path):
                os.mkdir(path)

            resp.status.result = Status.SUCCESS

        return resp

    '''
    load()
    Load the contents of a Librarian file as a string.
    '''
    def load(self, req):
        resp = LoadResponse()
        if len(req.type) == 0:
                resp.status.result = Status.FAILURE
                resp.status.error = Status.TYPE_MISSING
                resp.status.info = "No type provided!"
        else:
            path = join(self._root, req.type)
            filename = join(path, req.id)

            if not os.path.exists(path):
                resp.status.result = Status.FAILURE
                resp.status.error = Status.NO_SUCH_TYPE
                resp.status.info = "Type {} does not exist!".format(req.type)
            elif not os.path.exists(filename):
                resp.status.result = Status.FAILURE
                resp.status.error = Status.FILE_MISSING
                resp.status.info = "File {} does not exist as a member of type {}!".format(req.id, req.type)
            else:
                inf = open(filename, 'r')
                resp.text = inf.read()

                resp.status.result = Status.SUCCESS

        return resp

    '''
    load_params()
    Load onto the parameter server.
    '''
    def load_params(self, req):
        """ EXAMPLE OF LOADING PARAMETERS FROM A YAML FILE:
        paramlist=rosparam.load_file("/path/to/myfile",default_namespace="my_namespace")
        for params, ns in paramlist:
            rosparam.upload_params(ns,params)
        """
        resp = LoadResponse()
        if len(req.type) == 0:
                resp.status.result = Status.FAILURE
                resp.status.error = Status.TYPE_MISSING
                resp.status.info = "No type provided!"
        else:
            path = join(self._root, req.type)
            filename = join(path, req.id)

            if not os.path.exists(path):
                resp.status.result = Status.FAILURE
                resp.status.error = Status.NO_SUCH_TYPE
                resp.status.info = "Type {} does not exist!".format(req.type)
            elif not os.path.exists(filename):
                resp.status.result = Status.FAILURE
                resp.status.error = Status.FILE_MISSING
                resp.status.info = "File {} does not exist as a member of type {}!".format(req.id, req.type)
            else:
                paramlist = rosparam.load_file(filename)
                for params, ns in paramlist:
                    rosparam.upload_params(ns, params)

                resp.status.result = Status.SUCCESS

        return resp

    '''
    get_list()
    Returns the contents of a list as a list of strings.
    '''
    def get_list(self, req):
        resp = ListResponse()
        if len(req.type) == 0:
            path = self._root
        else:
            path = join(self._root, req.type)

        if not os.path.exists(path):
            resp.status.result = Status.FAILURE
            resp.status.error = Status.FILE_MISSING
            resp.status.info = "Could not find directory '{}'".format(path)
        else:
            resp.entries = os.listdir(path)
            resp.status.result = Status.SUCCESS
            resp.status.error = Status.NO_ERROR

        return resp

    def write_records(self):
        pass

    def load_records(self):
        pass

if __name__ == '__main__':
    rospy.init_node('librarian_core')

    # spin_rate = rospy.get_param('rate',10)
    # rate = rospy.Rate(spin_rate)

    try:
        lib = Librarian()

        rospy.spin()

    except rospy.ROSInterruptException:
        # shut down the node!
        # finish pending writes/reads
        # save the current state of the world

        pass
