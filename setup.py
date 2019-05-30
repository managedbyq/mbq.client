import codecs
import os

import setuptools


here = os.path.abspath(os.path.dirname(__file__))


with codecs.open('README.rst', 'r', 'utf-8') as f:
    readme = f.read()

about = {}
with codecs.open(os.path.join(here, 'mbq', 'client', '__version__.py'), 'r', 'utf-8') as f:
    exec(f.read(), about)

setuptools.setup(
    name=about['__title__'],
    description=about['__description__'],
    long_description=readme,
    long_description_content_type='text/x-rst',
    version=about['__version__'],
    license=about['__license__'],
    url=about['__url__'],
    author=about['__author__'],
    author_email=about['__author_email__'],
    maintainer=about['__author__'],
    maintainer_email=about['__author_email__'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Software Development :: Libraries',
    ],
    install_requires=[
        'dataclasses>=0.6',
        'mbq.metrics>=1.1.2',
        'requests>=2.21.0,<3.0.0',
        'typing_extensions>=3.7.2',
    ],
    keywords='token access authorization',
    packages=setuptools.find_packages(),
    include_package_data=True,
    zip_safe=False,
)
