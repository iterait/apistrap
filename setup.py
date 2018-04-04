from pip.req import parse_requirements
from setuptools import setup, find_packages

setup(name='api-utils',
      version='0.1.0',
      description='API utils',
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'Operating System :: Unix',
          'Programming Language :: Python :: Implementation :: CPython',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 3.6'
      ],
      keywords='api rest http',
      url='https://github.com/cognexa/api-utils',
      author='Cognexa Solutions s.r.o.',
      author_email='info@cognexa.com',
      license='MIT',
      packages=find_packages(".", exclude="tests"),
      include_package_data=True,
      zip_safe=False,
      setup_requires=['pytest-runner'],
      tests_require=['pytest'],
      install_requires=[str(ir.req) for ir in parse_requirements('requirements.txt', session='hack')],
      )
