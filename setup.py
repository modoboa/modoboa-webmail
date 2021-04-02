#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
"""

import io
from os import path
try:
    from pip.req import parse_requirements
except ImportError:
    # pip >= 10
    from pip._internal.req import parse_requirements
from setuptools import setup, find_packages


def get_requirements(requirements_file):
    """Use pip to parse requirements file."""
    requirements = []
    if path.isfile(requirements_file):
        for req in parse_requirements(requirements_file, session="hack"):
            try:
                # check markers, such as
                #
                #     rope_py3k    ; python_version >= '3.0'
                #
                if req.match_markers():
                    requirements.append(str(req.req))
            except AttributeError:
                # pip >= 20.0.2
                requirements.append(req.requirement)
    return requirements


if __name__ == "__main__":
    HERE = path.abspath(path.dirname(__file__))
    INSTALL_REQUIRES = get_requirements(path.join(HERE, "requirements.txt"))

    with io.open(path.join(HERE, "README.rst"), encoding="utf-8") as readme:
        LONG_DESCRIPTION = readme.read()

    def local_scheme(version):
        """Skip the local version (eg. +xyz of 0.6.1.dev4+gdf99fe2)
            to be able to upload to Test PyPI"""
        return ""

    setup(
        name="modoboa-webmail",
        description="The webmail of Modoboa",
        long_description=LONG_DESCRIPTION,
        license="MIT",
        url="http://modoboa.org/",
        author="Antoine Nguyen",
        author_email="tonio@ngyn.org",
        classifiers=[
            "Development Status :: 5 - Production/Stable",
            "Environment :: Web Environment",
            "Framework :: Django :: 2.2",
            "Intended Audience :: System Administrators",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.5",
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8",
            "Topic :: Communications :: Email",
            "Topic :: Internet :: WWW/HTTP",
        ],
        keywords="email webmail",
        packages=find_packages(exclude=["docs", "test_project"]),
        include_package_data=True,
        zip_safe=False,
        install_requires=INSTALL_REQUIRES,
        use_scm_version={"local_scheme": local_scheme},
        setup_requires=["setuptools_scm"],
    )
