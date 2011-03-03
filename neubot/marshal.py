# neubot/marshal.py

#
# Copyright (c) 2011 Simone Basso <bassosimone@gmail.com>,
#  NEXA Center for Internet & Society at Politecnico di Torino
#
# This file is part of Neubot <http://www.neubot.org/>.
#
# Neubot is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Neubot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Neubot.  If not, see <http://www.gnu.org/licenses/>.
#

import xml.dom.minidom
import types
import sys
import cgi

if __name__ == "__main__":
    sys.path.insert(0, ".")

from neubot.log import LOG

def XML_append_attribute(document, element, name, value):

    """
    Append to `element` an element with tagName `name` that contains
    a text node with value `value`.  All nodes are created in the context
    of the document `document`.  While at it, we also try to indent
    the resulting XML file in a way similar to what Firefox does in order
    to make it more human readable.
    """

    indent = document.createTextNode("    ")
    element.appendChild(indent)

    child_element = document.createElement(name)
    element.appendChild(child_element)

    text_node = document.createTextNode(value)
    child_element.appendChild(text_node)

    newline = document.createTextNode("\r\n")
    element.appendChild(newline)

SIMPLETYPES = [ types.IntType, types.FloatType, types.StringType,
                types.UnicodeType ]

def XML_marshal(object, root_elem_name):

    """
    Marshal the attributes of `object` into XML.  Note that this method
    will marshal scalar attributes only--vectors, hashes, and classes are
    going to be ignored.
    """

    document = xml.dom.minidom.parseString("<" + root_elem_name + "/>")

    root = document.documentElement
    newline = document.createTextNode("\r\n")
    root.appendChild(newline)

    #
    # Note that vars() works as long as the class has been
    # created using __init__() to initialize attributes.
    #

    allvars = vars(object)
    for name, value in allvars.items():
        if type(value) not in SIMPLETYPES:
            continue
        XML_append_attribute(document, root, name, str(value))
        continue

    try:
        data = root.toxml("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        LOG.exception()
        LOG.warning("Unicode endode or decode error (see above)")

        #
        # Return a non XML string so that the parser will notice
        # and will -hopefully- complain aloud.
        #

        data = ""

    return data

def QS_unmarshal(object, data):

    """
    Unmarshal the content of data -- which must be a www-urlencoded
    string -- into the given object, provided that the object already
    contains an attribute with such name and the same type.
    """

    dictionary = cgi.parse_qs(data)
    for key in dictionary:

        if not hasattr(object, key):
            continue

        value = getattr(object, key)
        if type(value) == types.IntType:
            cast = int
        elif type(value) == types.FloatType:
            cast = float
        elif type(value) == types.StringType:
            cast = str
        elif type(value) == types.UnicodeType:
            cast = unicode
        else:
            continue

        orig = dictionary[key][0]
        try:
            value = cast(orig)
        except ValueError:
            continue

        setattr(object, key, value)

__all__ = [ "XML_marshal", "QS_unmarshal" ]

class TestClass(object):
    def __init__(self):
        self.floating = 1.1
        self.func = lambda: None
        self.integer = 0
        self.string = "string"
        self.ustring = u"ustring"

if __name__ == "__main__":
    test = TestClass()
    print XML_marshal(test, "TestClass")

    QS_unmarshal(test, "floating=3.0&integer=2&string=asd&ustring=")
    print XML_marshal(test, "TestClass")

    QS_unmarshal(test, "floating=three&integer=two&string=&ustring=be")
    print XML_marshal(test, "TestClass")