"""A notebook manager that uses the local file system for storage.

Authors:

* Brian Granger
* Zach Sailer
"""

#-----------------------------------------------------------------------------
#  Copyright (C) 2011  The IPython Development Team
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

import datetime
import io
import os
import glob
import shutil

from unicodedata import normalize

from tornado import web

from .nbmanager import NotebookManager
from IPython.nbformat import current
from IPython.utils.traitlets import Unicode, Dict, Bool, TraitError
from IPython.utils import tz

#-----------------------------------------------------------------------------
# Classes
#-----------------------------------------------------------------------------

class FileNotebookManager(NotebookManager):
    
    save_script = Bool(False, config=True,
        help="""Automatically create a Python script when saving the notebook.
        
        For easier use of import, %run and %load across notebooks, a
        <notebook-name>.py script will be created next to any
        <notebook-name>.ipynb on each save.  This can also be set with the
        short `--script` flag.
        """
    )
    
    checkpoint_dir = Unicode(config=True,
        help="""The location in which to keep notebook checkpoints
        
        By default, it is notebook-dir/.ipynb_checkpoints
        """
    )
    def _checkpoint_dir_default(self):
        return os.path.join(self.notebook_dir, '.ipynb_checkpoints')
    
    def _checkpoint_dir_changed(self, name, old, new):
        """do a bit of validation of the checkpoint dir"""
        if not os.path.isabs(new):
            # If we receive a non-absolute path, make it absolute.
            abs_new = os.path.abspath(new)
            self.checkpoint_dir = abs_new
            return
        if os.path.exists(new) and not os.path.isdir(new):
            raise TraitError("checkpoint dir %r is not a directory" % new)
        if not os.path.exists(new):
            self.log.info("Creating checkpoint dir %s", new)
            try:
                os.mkdir(new)
            except:
                raise TraitError("Couldn't create checkpoint dir %r" % new)

    def get_notebook_names(self, path='/'):
        """List all notebook names in the notebook dir and path."""
        names = glob.glob(self.get_os_path('*'+self.filename_ext, path))
        names = [os.path.basename(name)
                 for name in names]
        return names

    def increment_filename(self, basename, path='/'):
        """Return a non-used filename of the form basename<int>."""
        i = 0
        while True:
            name = u'%s%i.ipynb' % (basename,i)
            os_path = self.get_os_path(name, path)
            if not os.path.isfile(os_path):
                break
            else:
                i = i+1
        return name

    def notebook_exists(self, name, path='/'):
        """Returns a True if the notebook exists. Else, returns False.

        Parameters
        ----------
        name : string
            The name of the notebook you are checking.
        path : string
            The relative path to the notebook (with '/' as separator)

        Returns
        -------
        bool
        """
        path = self.get_os_path(name, path='/')
        return os.path.isfile(path)

    def list_notebooks(self, path):
        """Returns a list of dictionaries that are the standard model
        for all notebooks in the relative 'path'.
        
        Parameters
        ----------
        path : str
            the URL path that describes the relative path for the
            listed notebooks
        
        Returns
        -------
        notebooks : list of dicts
            a list of the notebook models without 'content'
        """
        notebook_names = self.get_notebook_names(path)
        notebooks = []
        for name in notebook_names:
            model = self.get_notebook_model(name, path, content=False)
            notebooks.append(model)
        notebooks = sorted(notebooks, key=lambda item: item['name'])
        return notebooks

    def get_notebook_model(self, name, path='/', content=True):
        """ Takes a path and name for a notebook and returns it's model
        
        Parameters
        ----------
        name : str
            the name of the notebook
        path : str
            the URL path that describes the relative path for
            the notebook
            
        Returns
        -------
        model : dict
            the notebook model. If contents=True, returns the 'contents' 
            dict in the model as well.
        """
        os_path = self.get_os_path(name, path)
        if not os.path.isfile(os_path):
            raise web.HTTPError(404, u'Notebook does not exist: %s' % name)
        info = os.stat(os_path)
        last_modified = tz.utcfromtimestamp(info.st_mtime)
        # Create the notebook model.
        model ={}
        model['name'] = name
        model['path'] = path
        model['last_modified'] = last_modified
        if content is True:
            with open(os_path, 'r') as f:
                try:
                    nb = current.read(f, u'json')
                except Exception as e:
                    raise web.HTTPError(400, u"Unreadable Notebook: %s %s" % (os_path, e))
            model['content'] = nb
        return model

    def save_notebook_model(self, model, name, path='/'):
        """Save the notebook model and return the model with no content."""

        if 'content' not in model:
            raise web.HTTPError(400, u'No notebook JSON data provided')

        new_path = model.get('path', path)
        new_name = model.get('name', name)

        if path != new_path or name != new_name:
            self.rename_notebook(name, path, new_name, new_path)

        # Save the notebook file
        os_path = self.get_os_path(new_name, new_path)
        nb = current.to_notebook_json(model['content'])
        if 'name' in nb['metadata']:
            nb['metadata']['name'] = u''
        try:
            self.log.debug("Autosaving notebook %s", os_path)
            with open(os_path, 'w') as f:
                current.write(nb, f, u'json')
        except Exception as e:
            raise web.HTTPError(400, u'Unexpected error while autosaving notebook: %s %s' % (os_path, e))

        # Save .py script as well
        if self.save_script:
            py_path = os.path.splitext(os_path)[0] + '.py'
            self.log.debug("Writing script %s", py_path)
            try:
                with io.open(py_path, 'w', encoding='utf-8') as f:
                    current.write(model, f, u'py')
            except Exception as e:
                raise web.HTTPError(400, u'Unexpected error while saving notebook as script: %s %s' % (py_path, e))

        model = self.get_notebook_model(name, path, content=False)
        return model

    def update_notebook_model(self, model, name, path='/'):
        """Update the notebook's path and/or name"""
        new_name = model.get('name', name)
        new_path = model.get('path', path)
        if path != new_path or name != new_name:
            self.rename_notebook(name, path, new_name, new_path)
        model = self.get_notebook_model(new_name, new_path, content=False)
        return model

    def delete_notebook_model(self, name, path='/'):
        """Delete notebook by name and path."""
        os_path = self.get_os_path(name, path)
        if not os.path.isfile(os_path):
            raise web.HTTPError(404, u'Notebook does not exist: %s' % os_path)
        
        # clear checkpoints
        for checkpoint in self.list_checkpoints(name, path):
            checkpoint_id = checkpoint['checkpoint_id']
            cp_path = self.get_checkpoint_path(checkpoint_id, name, path)
            if os.path.isfile(cp_path):
                self.log.debug("Unlinking checkpoint %s", cp_path)
                os.unlink(cp_path)
        
        self.log.debug("Unlinking notebook %s", os_path)
        os.unlink(os_path)

    def rename_notebook(self, old_name, old_path, new_name, new_path):
        """Rename a notebook."""
        if new_name == old_name and new_path == old_path:
            return
        
        new_os_path = self.get_os_path(new_name, new_path)
        old_os_path = self.get_os_path(old_name, old_path)

        # Should we proceed with the move?
        if os.path.isfile(new_os_path):
            raise web.HTTPError(409, u'Notebook with name already exists: %s' % new_os_path)
        if self.save_script:
            old_py_path = os.path.splitext(old_os_path)[0] + '.py'
            new_py_path = os.path.splitext(new_os_path)[0] + '.py'
            if os.path.isfile(new_py_path):
                raise web.HTTPError(409, u'Python script with name already exists: %s' % new_py_path)

        # Move the notebook file
        try:
            os.rename(old_os_path, new_os_path)
        except Exception as e:
            raise web.HTTPError(400, u'Unknown error renaming notebook: %s %s' % (old_os_path, e))

        # Move the checkpoints
        old_checkpoints = self.list_checkpoints(old_name, old_path)
        for cp in old_checkpoints:
            checkpoint_id = cp['checkpoint_id']
            old_cp_path = self.get_checkpoint_path(checkpoint_id, old_name, old_path)
            new_cp_path = self.get_checkpoint_path(checkpoint_id, new_name, new_path)
            if os.path.isfile(old_cp_path):
                self.log.debug("Renaming checkpoint %s -> %s", old_cp_path, new_cp_path)
                os.rename(old_cp_path, new_cp_path)

        # Move the .py script
        if self.save_script:
            os.rename(old_py_path, new_py_path)
  
    # Checkpoint-related utilities
    
    def get_checkpoint_path(self, checkpoint_id, name, path='/'):
        """find the path to a checkpoint"""
        filename = u"{name}-{checkpoint_id}{ext}".format(
            name=name,
            checkpoint_id=checkpoint_id,
            ext=self.filename_ext,
        )
        cp_path = os.path.join(path, self.checkpoint_dir, filename)
        return cp_path

    def get_checkpoint_model(self, checkpoint_id, name, path='/'):
        """construct the info dict for a given checkpoint"""
        cp_path = self.get_checkpoint_path(checkpoint_id, name, path)
        stats = os.stat(cp_path)
        last_modified = tz.utcfromtimestamp(stats.st_mtime)
        info = dict(
            checkpoint_id = checkpoint_id,
            last_modified = last_modified,
        )
        return info
        
    # public checkpoint API
    
    def create_checkpoint(self, name, path='/'):
        """Create a checkpoint from the current state of a notebook"""
        nb_path = self.get_os_path(name, path)
        # only the one checkpoint ID:
        checkpoint_id = u"checkpoint"
        cp_path = self.get_checkpoint_path(checkpoint_id, name, path)
        self.log.debug("creating checkpoint for notebook %s", name)
        if not os.path.exists(self.checkpoint_dir):
            os.mkdir(self.checkpoint_dir)
        shutil.copy2(nb_path, cp_path)
        
        # return the checkpoint info
        return self.get_checkpoint_model(checkpoint_id, name, path)
    
    def list_checkpoints(self, name, path='/'):
        """list the checkpoints for a given notebook
        
        This notebook manager currently only supports one checkpoint per notebook.
        """
        checkpoint_id = "checkpoint"
        path = self.get_checkpoint_path(checkpoint_id, name, path)
        if not os.path.exists(path):
            return []
        else:
            return [self.get_checkpoint_model(checkpoint_id, name, path)]
        
    
    def restore_checkpoint(self, checkpoint_id, name, path='/'):
        """restore a notebook to a checkpointed state"""
        self.log.info("restoring Notebook %s from checkpoint %s", name, checkpoint_id)
        nb_path = self.get_os_path(name, path)
        cp_path = self.get_checkpoint_path(checkpoint_id, name, path)
        if not os.path.isfile(cp_path):
            self.log.debug("checkpoint file does not exist: %s", cp_path)
            raise web.HTTPError(404,
                u'Notebook checkpoint does not exist: %s-%s' % (name, checkpoint_id)
            )
        # ensure notebook is readable (never restore from an unreadable notebook)
        with file(cp_path, 'r') as f:
            nb = current.read(f, u'json')
        shutil.copy2(cp_path, nb_path)
        self.log.debug("copying %s -> %s", cp_path, nb_path)
    
    def delete_checkpoint(self, checkpoint_id, name, path='/'):
        """delete a notebook's checkpoint"""
        cp_path = self.get_checkpoint_path(checkpoint_id, name, path)
        if not os.path.isfile(cp_path):
            raise web.HTTPError(404,
                u'Notebook checkpoint does not exist: %s%s-%s' % (path, name, checkpoint_id)
            )
        self.log.debug("unlinking %s", cp_path)
        os.unlink(cp_path)
    
    def info_string(self):
        return "Serving notebooks from local directory: %s" % self.notebook_dir
