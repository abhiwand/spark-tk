"""
Post-processes HTML generated by pdoc
"""
import re
import datetime
import os
import sys
import shutil
import tempfile
import logging
logger = logging.getLogger(__file__)


def pre_process_py(path):

    def go(full_name, reader, writer):
        text = reader.read()
        output = str(DocExamplesPreprocessor(text, mode='doc', file_name=full_name))
        writer.write(output)
    walk_path(path, '.py', go)


def post_process_html(path):

    def go(full_name, reader, writer):
        for line in reader.readlines():
            processed_line = process_html_line(line, full_name)
            writer.write(processed_line)
    walk_path(path, '.html', go)


def walk_path(path, suffixes, processor):
    """walks the path_to_examples and creates paths to all the .rst files found"""
    logger.debug("walk_path(path='%s', suffixes=%s)", path, suffixes)
    for root, dir_names, file_names in os.walk(path):
        logger.debug("walk_path: file_names=%s", file_names)
        for file_name in file_names:
            if file_name.endswith(suffixes):
                full_name = os.path.join(root, file_name)
                logger.debug("walk_path: processing file %s", full_name)
                with open(full_name, 'r') as r:
                    with tempfile.NamedTemporaryFile(delete=False) as w:
                        tmp_name = w.name
                        logger.debug("walk_path: tmp_name=%s", tmp_name)
                        processor(full_name, r, w)
                os.remove(full_name)
                shutil.move(tmp_name, full_name)


def process_html_line(line, full_name):

    # Repair the "Up" link for certain files (this needs to match the doc/templates/css.mako)
    if full_name.endswith("/index.html") and '<a href="index.html" id="fixed_top_left">Up</a>' in line:
        if full_name.endswith("/sparktk/index.html"):
            return '  <!-- No Up for root level index.html -->\n'
        return '<a href="../index.html" id="fixed_top_left">Up</a>\n'

    # clean doctest flags
    return line


def parse_for_doc(text, file_name=None):
    return str(DocExamplesPreprocessor(text, mode='doc', file_name=file_name))


def parse_for_doctest(text, file_name=None):
    return str(DocExamplesPreprocessor(text, mode='doctest', file_name=file_name))


class DocExamplesException(Exception):
    """Exception specific to processing documentation examples"""
    pass


class DocExamplesPreprocessor(object):
    """
    Processes text (intended for Documentation Examples) and applies ATK doc markup, mostly to enable doctest testing
    """

    doctest_ellipsis = '-etc-'  # override for the doctest ELLIPSIS_MARKER

    # multi-line tags
    hide_start_tag = '<hide>'
    hide_stop_tag = '</hide>'
    skip_start_tag = '<skip>'
    skip_stop_tag = '</skip>'

    # replacement tags
    doc_replacements = [('<progress>', '[===Job Progress===]'),
                        ('<connect>', 'Connected ...'),
                        ('<datetime.datetime>', repr(datetime.datetime.now())),
                        ('<blankline>', '<BLANKLINE>')]   # sphinx will ignore this for us

    doctest_replacements = [('<progress>', doctest_ellipsis),
                            ('<connect>', doctest_ellipsis),
                            ('<datetime.datetime>', doctest_ellipsis),
                            ('<blankline>', '<BLANKLINE>')]

    # Two simple fsms, each with 2 states:  Keep, Drop
    keep = 0
    drop = 1

    def __init__(self, text, mode='doc', file_name=None):
        """
        :param text: str of text to process
        :param mode:  preprocess mode, like 'doc' or 'doctest'
        :return: object whose __str__ is the processed example text
        """
        if mode == 'doc':
            # process for human-consumable documentation
            self.replacements = self.doc_replacements
            self.is_state_keep = self._is_hide_state_keep
            self._disappear  = ''   # in documentation, we need complete disappearance
        elif mode == 'doctest':
            # process for doctest execution
            self.replacements = self.doctest_replacements
            self.is_state_keep = self._is_skip_state_keep
            self._disappear = '\n'  # disappear means blank line for doctests, to preserve line numbers for error report
        else:
            raise DocExamplesException('Invalid mode "%s" given to %s.  Must be in %s' %
                                       (mode, self.__class__, ", ".join(['doc', 'doctest'])))
        self.skip_state = self.keep
        self.hide_state = self.keep
        self.processed = ''
        self._file_name = file_name

        if text:
            lines = text.splitlines(True)
            self.processed = ''.join(self._process_line(line) for line in lines)
            if self.hide_state != self.keep:
                raise DocExamplesException("unclosed tag %s found%s" % (self.hide_start_tag, self._in_file()))
            if self.skip_state != self.keep:
                raise DocExamplesException("unclosed tag %s found" % self.skip_start_tag, self._in_file())

    def _in_file(self):
        return (" in file %s" % self._file_name) if self._file_name else ''

    def _is_skip_state_keep(self):
        return self.skip_state == self.keep

    def _is_hide_state_keep(self):
        return self.hide_state == self.keep

    def _process_line(self, line):
        """processes line and advances fsms as necessary, returns processed line text"""
        stripped = line.lstrip()
        if stripped:

            # Repair the "Up" link for certain files (this needs to match the doc/templates/css.mako)
            if self._file_name and self._file_name.endswith("/index.html") and '<a href="index.html" id="fixed_top_left">Up</a>' in line:
                if self._file_name.endswith("/sparktk/index.html"):
                    return '  <!-- No Up for root level index.html -->\n'
                return '<a href="../index.html" id="fixed_top_left">Up</a>\n'

            stripped = DocExamplesPreprocessor._strip_markdown_comment(stripped)
            if stripped[0] == '<':
                if self._process_if_tag_pair_tag(stripped):
                    return self._disappear  # tag-pair markup should disappear appropriately

                # check for keyword replacement
                for keyword, replacement in self.replacements:
                    if stripped.startswith(keyword):
                        line = line.replace(keyword, replacement, 1)
                        break

        return line if self.is_state_keep() else self._disappear

    def _process_if_tag_pair_tag(self, stripped):
        """determines if the stripped line is a tag pair start or stop, advances fsms accordingly"""
        if stripped.startswith(self.skip_start_tag):
            if self.skip_state == self.drop:
                raise DocExamplesException("nested tag %s found%s" % (self.skip_start_tag, self._in_file()))
            self.skip_state = self.drop
            return True
        elif stripped.startswith(self.skip_stop_tag):
            if self.skip_state == self.keep:
                raise DocExamplesException("unexpected tag %s found%s" % (self.skip_stop_tag, self._in_file()))
            self.skip_state = self.keep
            return True
        elif stripped.startswith(self.hide_start_tag):
            if self.hide_state == self.drop:
                raise DocExamplesException("nested tag %s found%s" % (self.hide_start_tag, self._in_file()))
            self.hide_state = self.drop
            return True
        elif stripped.startswith(self.hide_stop_tag):
            if self.hide_state == self.keep:
                raise DocExamplesException("unexpected tag %s found%s" % (self.hide_stop_tag, self._in_file()))
            self.hide_state = self.keep
            return True
        return False

    markdown_comment_tell = r'[//]:'
    markdown_comment_re = r'^\[//\]:\s*#\s*\"(.+)\"$'
    markdown_comment_pattern = re.compile(markdown_comment_re)

    @staticmethod
    def _strip_markdown_comment(s):
        """
        Checks if the given string is formatted as a Markdown comment per Magnus' response here:
        http://stackoverflow.com/questions/4823468/comments-in-markdown/32190021#32190021

        If it is, the formatting is stripped and only the comment's content is returned
        If not, the string is returned untouched
        """
        if s.startswith(DocExamplesPreprocessor.markdown_comment_tell):
            m = DocExamplesPreprocessor.markdown_comment_pattern.match(s)
            if m:
                return m.group(1)
        return s

    def __str__(self):
        return self.processed

##########################################################

def main():
    script_name = os.path.basename(__file__)
    usage = "Usage: %s <-html=HTML_DIR|-py=PY_DIR>" % script_name

    if len(sys.argv) < 2:
        raise RuntimeError(usage)

    option = sys.argv[1]
    html_flag = '-html='
    py_flag = '-py='

    if option.startswith(html_flag):
        value = option[len(html_flag):]
        html_dir = os.path.abspath(value)
        print "[%s] processing HTML at %s" % (script_name, html_dir)
        post_process_html(html_dir)
    elif option.startswith(py_flag):
        value = option[len(py_flag):]
        py_dir = os.path.abspath(value)
        print "[%s] processing Python at %s" % (script_name, py_dir)
        pre_process_py(py_dir)
    else:
        raise RuntimeError(usage)


if __name__ == "__main__":
    main()
