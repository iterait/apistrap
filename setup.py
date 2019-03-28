from setuptools import find_packages, setup

setup(name='apistrap',
      version='0.3.1',
      description='Iterait REST API utilities',
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'Operating System :: Unix',
          'Programming Language :: Python :: Implementation :: CPython',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
      ],
      keywords='api rest http',
      url='https://github.com/iterait/apistrap',
      author=['Iterait a.s.', 'Cognexa Solutions s.r.o.'],
      author_email='hello@iterait.com',
      license='MIT',
      packages=find_packages('.', exclude='tests'),
      package_data={
          'apistrap': ['templates/*.html']
      },
      zip_safe=False,
      setup_requires=['pytest-runner'],
      tests_require=['pytest', 'pytest-mock', 'pytest-flask', 'pytest-aiohttp'],
      install_requires=['apispec', 'schematics', 'more_itertools'],
      extras_require={
          'flask': ['flask'],
          'aiohttp': ['aiohttp']
      })
