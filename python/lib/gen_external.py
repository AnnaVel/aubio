import distutils.ccompiler
import os, subprocess, glob

header = os.path.join('src', 'aubio.h')
output_path = os.path.join('python', 'gen')

source_header = """// this file is generated! do not modify
#include "aubio-types.h"
"""

skip_objects = [
  # already in ext/
  'fft',
  'pvoc',
  'filter',
  'filterbank',
  #'resampler',
  # AUBIO_UNSTABLE
  'hist',
  'parameter',
  'scale',
  'beattracking',
  'resampler',
  'peakpicker',
  'pitchfcomb',
  'pitchmcomb',
  'pitchschmitt',
  'pitchspecacf',
  'pitchyin',
  'pitchyinfft',
  'sink',
  'sink_apple_audio',
  'sink_sndfile',
  'sink_wavwrite',
  #'mfcc',
  'source',
  'source_apple_audio',
  'source_sndfile',
  'source_avcodec',
  'source_wavread',
  #'sampler',
  'audio_unit',

  'tss',
  ]

def get_cpp_objects(header=header):
    include_file = os.path.basename(header)

    # findout which compiler to use
    from distutils.sysconfig import customize_compiler
    compiler_name = distutils.ccompiler.get_default_compiler()
    compiler = distutils.ccompiler.new_compiler(compiler=compiler_name)
    try:
        customize_compiler(compiler)
    except AttributeError as e:
        print("Warning: failed customizing compiler.")
        pass

    cpp_cmd = None
    if hasattr(compiler, 'preprocessor'): # for unixccompiler
        cpp_cmd = compiler.preprocessor
    elif hasattr(compiler, 'compiler'): # for ccompiler
        cpp_cmd = compiler.compiler
    elif hasattr(compiler, 'cc'): # for msvccompiler
        cpp_cmd = compiler.cc
    elif hasattr(compiler, 'find_exe'):
        cpp_cmd = [compiler.find_exe('cl.exe')]
        cpp_cmd += ['/E']

    if not cpp_cmd:
        print("Warning: could not guess preprocessor, using env's CC")
        print("Compiler was: " + type(compiler))
        print("Compiler attrs: " + dir(compiler))
        if sys.platform.startswith('win'):
            cpp_cmd = ['cl.exe']
            cpp_cmd += ['/E']
        else:
            cpp_cmd = os.environ.get('CC', 'cc').split()
            cpp_cmd += ['-E']

    macros = [('AUBIO_UNSTABLE', 1)]

    if os.path.isfile(header):
        include_path = os.path.dirname(header)
        include_file = os.path.basename(header)
    else:
        raise Exception("could not find include file " + header)

    includes = [os.path.dirname(header)]
    cpp_cmd += ['-P']
    cpp_cmd += distutils.ccompiler.gen_preprocess_options(macros, includes)
    cpp_cmd += [header]

    print("Running command: {:s}".format(" ".join(cpp_cmd)))
    proc = subprocess.Popen(cpp_cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE)
    assert proc, 'Proc was none'
    cpp_output = proc.stdout.read()
    err_output = proc.stderr.read()
    if compiler_name in ['msvc']:
        guessed_output = os.path.splitext(os.path.basename(include_file))[0]+".i"
        cpp_output = [l.strip() for l in open(guessed_output, 'r').readlines()]
    if not cpp_output:
        raise Exception("preprocessor output is empty:\n%s" % err_output)
    elif err_output:
        print ("Warning: preprocessor produced errors\n%s" % err_output)
    #cpp_output = [l.strip() for l in os.popen(" ".join(cpp_cmd)).readlines()]
    if not isinstance(cpp_output, list):
        cpp_output = [l.strip() for l in cpp_output.decode('utf8').split('\n')]

    cpp_output = filter(lambda y: len(y) > 1, cpp_output)
    cpp_output = filter(lambda y: not y.startswith('#'), cpp_output)
    cpp_output = list(cpp_output)

    i = 1
    while 1:
        if i >= len(cpp_output): break
        if cpp_output[i-1].endswith(',') or cpp_output[i-1].endswith('{') or cpp_output[i].startswith('}'):
            cpp_output[i] = cpp_output[i-1] + ' ' + cpp_output[i]
            cpp_output.pop(i-1)
        else:
            i += 1

    typedefs = filter(lambda y: y.startswith ('typedef struct _aubio'), cpp_output)

    cpp_objects = [a.split()[3][:-1] for a in typedefs]

    return cpp_output, cpp_objects

def generate_external(header=header, output_path=output_path, usedouble=False, overwrite=True):
    if not os.path.isdir(output_path): os.mkdir(output_path)
    elif overwrite == False: return glob.glob(os.path.join(output_path, '*.c'))
    sources_list = []
    cpp_output, cpp_objects = get_cpp_objects(header)
    lib = {}

    for o in cpp_objects:
        if o[:6] != 'aubio_':
            continue
        shortname = o[6:-2]
        if shortname in skip_objects:
            continue
        lib[shortname] = {'struct': [], 'new': [], 'del': [], 'do': [], 'get': [], 'set': [], 'other': []}
        lib[shortname]['longname'] = o
        lib[shortname]['shortname'] = shortname
        for fn in cpp_output:
            if o[:-1] in fn:
                #print "found", o[:-1], "in", fn
                if 'typedef struct ' in fn:
                    lib[shortname]['struct'].append(fn)
                elif '_do' in fn:
                    lib[shortname]['do'].append(fn)
                elif 'new_' in fn:
                    lib[shortname]['new'].append(fn)
                elif 'del_' in fn:
                    lib[shortname]['del'].append(fn)
                elif '_get_' in fn:
                    lib[shortname]['get'].append(fn)
                elif '_set_' in fn:
                    lib[shortname]['set'].append(fn)
                else:
                    #print "no idea what to do about", fn
                    lib[shortname]['other'].append(fn)

    """
    for fn in cpp_output:
        found = 0
        for o in lib:
            for family in lib[o]:
                if fn in lib[o][family]:
                    found = 1
        if found == 0:
            print "missing", fn

    for o in lib:
        for family in lib[o]:
            if type(lib[o][family]) == str:
                print ( "{:15s} {:10s} {:s}".format(o, family, lib[o][family] ) )
            elif len(lib[o][family]) == 1:
                print ( "{:15s} {:10s} {:s}".format(o, family, lib[o][family][0] ) )
            else:
                print ( "{:15s} {:10s} {:d}".format(o, family, len(lib[o][family]) ) )
    """

    try:
        from .gen_code import MappedObject
    except (SystemError, ValueError) as e:
        from gen_code import MappedObject
    for o in lib:
        out = source_header
        mapped = MappedObject(lib[o], usedouble = usedouble)
        out += mapped.gen_code()
        output_file = os.path.join(output_path, 'gen-%s.c' % o)
        with open(output_file, 'w') as f:
            f.write(out)
            print ("wrote %s" % output_file )
            sources_list.append(output_file)

    out = source_header
    out += "#include \"aubio-generated.h\""
    check_types = "\n     ||  ".join(["PyType_Ready(&Py_%sType) < 0" % o for o in lib])
    out += """

int generated_types_ready (void)
{{
  return ({pycheck_types});
}}
""".format(pycheck_types = check_types)

    add_types = "".join(["""
  Py_INCREF (&Py_{name}Type);
  PyModule_AddObject(m, "{name}", (PyObject *) & Py_{name}Type);""".format(name = o) for o in lib])
    out += """

void add_generated_objects ( PyObject *m )
{{
{add_types}
}}
""".format(add_types = add_types)

    output_file = os.path.join(output_path, 'aubio-generated.c')
    with open(output_file, 'w') as f:
        f.write(out)
        print ("wrote %s" % output_file )
        sources_list.append(output_file)

    objlist = "".join(["extern PyTypeObject Py_%sType;\n" % p for p in lib])
    out = """// generated list of objects created with gen_external.py

#include <Python.h>
"""
    if usedouble:
        out += """
#ifndef HAVE_AUBIO_DOUBLE
#define HAVE_AUBIO_DOUBLE 1
#endif
"""
    out += """
{objlist}
int generated_objects ( void );
void add_generated_objects( PyObject *m );
""".format(objlist = objlist)

    output_file = os.path.join(output_path, 'aubio-generated.h')
    with open(output_file, 'w') as f:
        f.write(out)
        print ("wrote %s" % output_file )
        # no need to add header to list of sources

    import sys
    py3 = sys.version_info[0] == 3
    if not py3:
        return [str(s) for s in sources_list]
    return sources_list

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1: header = sys.argv[1]
    if len(sys.argv) > 2: output_path = sys.argv[2]
    generate_external(header, output_path)
