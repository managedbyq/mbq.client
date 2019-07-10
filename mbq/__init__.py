# https://packaging.python.org/namespace_packages/#pkgutil-style-namespace-packages
import typing


__path__: typing.Iterable[str] = __import__('pkgutil').extend_path(__path__, __name__)
