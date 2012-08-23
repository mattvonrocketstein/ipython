"""Various display related classes.

Authors : MinRK, gregcaporaso
"""

from IPython.display import display, HTML
from os import walk
from os.path import join, exists, isfile, splitext


class YouTubeVideo(object):
    """Class for embedding a YouTube Video in an IPython session, based on its video id.

    e.g. to embed the video on this page:

    http://www.youtube.com/watch?v=foo

    you would do:

    vid = YouTubeVideo("foo")
    display(vid)
    """

    def __init__(self, id, width=400, height=300):
        self.id = id
        self.width = width
        self.height = height

    def _repr_html_(self):
        """return YouTube embed iframe for this video id"""
        return """
            <iframe
                width="%i"
                height="%i"
                src="http://www.youtube.com/embed/%s"
                frameborder="0"
                allowfullscreen
            ></iframe>
        """%(self.width, self.height, self.id)

class LocalFile(object):
    """Class for embedding a local file link in an IPython session, based on path

    e.g. to embed a link that was generated in the IPython notebook as my/data.txt

    you would do:

    local_file = LocalFile("my/data.txt")
    display(local_file)
    """
    
    def __init__(self,
                 path,
                 _directory_prefix='files',
                 _result_html_prefix='',
                 _result_html_suffix='<br>'):
        """
            path : path to the file or directory that should be formatted
            directory_prefix : prefix to be prepended to all files to form a
             working link [default: 'files']
            result_html_prefix : text to append to beginning to link
             [default: none]
            result_html_suffix : text to append at the end of link
             [default: '<br>']
        """
        self.path = path
        self._directory_prefix = _directory_prefix
        self._link_str = "<a href='%s' target='_blank'>%s</a>"
        self._result_html_prefix = _result_html_prefix
        self._result_html_suffix = _result_html_suffix
    
    def _format_path(self):
        fp = join(self._directory_prefix,self.path)
        return ''.join([self._result_html_prefix,
                        self._link_str % (fp, self.path),
                        self._result_html_suffix])
        
    def _repr_html_(self):
        """return link to local file
        """
        if not exists(self.path):
            return ("Path (<tt>%s</tt>) doesn't exist. " 
                    "It may still be in the process of "
                    "being generated, or you may have the "
                    "incorrect path." % self.path)
        
        return self._format_path()

# Create an alias for formatting a single directory name as a link.
# Right now this is the same as a formatting for a single file, but 
# we'll encorage users to reference these with a different class in
# case we want to change this in the future.
LocalDirectory = LocalFile

class LocalFiles(LocalFile):
    """Class for embedding local file links in an IPython session, based on path

    e.g. to embed links to files that were generated in the IPython notebook under my/data

    you would do:

    local_files = LocalFiles("my/data")
    display(local_files)
    """
    def __init__(self,
                 path,
                 _directory_prefix='files',
                 _included_suffixes=None,
                 _result_html_prefix='',
                 _result_html_suffix='<br>'):
        """
            included_suffixes : list of filename suffixes to include when
             formatting output [default: include all files]
             
            See the LocalFile (baseclass of LocalDirectory) docstring for 
             information on additional parameters.
        """
        self._included_suffixes = _included_suffixes
        LocalFile.__init__(self,
                           path,
                           _directory_prefix,
                           _result_html_prefix,
                           _result_html_suffix)
    
    def _format_path(self):
        result_entries = []
        for root, dirs, files in walk(self.path):
            for fn in files:
                fp = join(self._directory_prefix,root,fn)
                # if all files are being included, or fp has a suffix
                # that is in included_suffix, create a link to fp
                if self._included_suffixes == None or \
                   splitext(fn)[1] in self._included_suffixes:
                    result_entries.append(''.join([self._result_html_prefix,
                                                   self._link_str % (fp,fn),
                                                   self._result_html_suffix]))
        return '\n'.join(result_entries)
