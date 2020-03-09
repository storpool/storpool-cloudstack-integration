#!/usr/bin/python3

"""Helper script for updating the version from an example pom.xml"""

import sys
import xml.etree.ElementTree as ET


def applyver(path, newversion=None):
    """
    path: file path to xml
    returns version str from path
    """
    namespaces = dict(
        [node for _, node in ET.iterparse(path, events=['start-ns'])]
    )
    tree = ET.parse(path)
    root = tree.getroot()
    for args in namespaces.items():
        ET.register_namespace(*args)
    parent = next(iter([i for i in root if i.tag.endswith('parent')]))
    version = next(iter([i for i in parent if i.tag.endswith('version')]))
    if newversion is None:
        return version.text
    version.text = newversion
    tree.write(path)
    return tree


def main():
    """parse args and update pom"""
    if len(sys.argv) < 3:
        sys.exit(
            f'Usage: {sys.argv[0]} <path-to-cs-client-pom.xml> '
            '<path-to-our-pom.xml-to-be-updated>'
        )
    cspom = sys.argv[1]
    ourpom = sys.argv[2]
    try:
        cspomversion = applyver(cspom)
    except ET.ParseError as err:
        sys.exit(f'Failed to parse {cspom}, error: {err}')

    try:
        applyver(ourpom, newversion=cspomversion)
    except ET.ParseError as err:
        sys.exit(f'Failed to parse/update {ourpom}, error: {err}')
    print(f'Successfully edited {ourpom} with {cspomversion}')


if __name__ == '__main__':
    main()
