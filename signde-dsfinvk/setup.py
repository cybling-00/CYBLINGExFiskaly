from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in cyblingexfiskaly/__init__.py
from cyblingexfiskaly import __version__ as version

setup(
	name="cyblingexfiskaly",
	version=version,
	description="CYBLINGExFISKALY",
	author="Codes Soft",
	author_email="shahid@codessoft.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
