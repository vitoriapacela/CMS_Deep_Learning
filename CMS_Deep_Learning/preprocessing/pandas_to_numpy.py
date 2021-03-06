import sys,os
from six import string_types
if __package__ is None:
    #sys.path.append(os.path.realpath("../"))
    sys.path.append(os.path.realpath(__file__+"/../../../"))


import time, math,re,h5py,shutil
import argparse
from multiprocessing import Process
from time import sleep
from CMS_Deep_Learning.preprocessing.preprocessing import size_from_meta,get_sizes_meta_dict

PARTICLE_OBSERVS = ['Energy', 'Px', 'Py', 'Pz', 'Pt', 'Eta', 'Phi', 'Charge',
                    'ChPFIso', 'GammaPFIso', 'NeuPFIso',
                    'isChHad', 'isEle', 'isGamma', 'isMu', 'isNeuHad',
                    'vtxX', 'vtxY', 'vtxZ']
HLF_OBSERVS = ['HT', 'MET', 'MT', 'PhiMET', 'bJets', 'nJets']
DEFAULT_RPE = {"Particles": 801, "HLF": 1}
DEFAULT_OBSERVS = {"Particles": PARTICLE_OBSERVS, "HLF": HLF_OBSERVS }

import pandas as pd
import numpy as np

#----------------------------IO-----------------------------
def get_from_pandas(f, file_start_read, samples_to_read, file_total_events=-1, observ_types=DEFAULT_OBSERVS,rows_per_event=DEFAULT_RPE):
    '''Helper Function - Gets a numpy array from a pandas .h5 file
    
        :param f: The filepath of the pandas file
        :type f: str
        :param file_start_read: what samples to start reading with
        :type file_start_read: uint
        :param samples_to_read: the number of samples to read
        :type samples_to_read: uint
        :param file_total_events: the total events in the file (if you know it)
        :type file_total_events: uint
        :param observ_types: A dictionary of the features (ordered) to get from pandas for each data type
        :type observ_types: dict
        :param rows_per_event: A dictionary of the number of rows per event for each data type
        :type rows_per_event: dict
        :returns: the numpy array
    '''
    store = pd.HDFStore(f)

    values = {}
    for key, rpe in rows_per_event.items():
        # Where to start reading the table based on the sum of the selection start 
        select_start = file_start_read * rpe
        select_stop = select_start + samples_to_read * rpe

        if (samples_to_read == file_total_events):
            frame = store.get('/' + key)
        else:
            frame = store.select('/' + key, start=select_start, stop=select_stop)

        columns = list(frame.columns)

        x = frame.values
        if (observ_types != None):
            x = np.take(x, [columns.index(o) for o in observ_types[key]], axis=-1)
        if (rpe > 1):
            n_rows, n_columns = x.shape
            x = x.reshape((n_rows / rpe, rpe, n_columns))

        values[key] = x
    store.close()
    return values
#------------------------------------------------------------


#---------------------------HELPERS---------------------------
def _gen_label_vecs(data_dirs):
    num_labels = len(data_dirs)
    label_vecs = {}
    for i, data_dir in enumerate(data_dirs):
        arr = np.zeros((num_labels,))
        arr[i] = 1
        label_vecs[data_dir] = arr
    return label_vecs


def _initializeArrays(data_dirs, samples_per_class):
    '''Helper Function - Generates the initial data structures for the X (data) and Y (target)'''
    num_classes = len(data_dirs)
    X_train = [None] * (samples_per_class * num_classes)
    y_train = [None] * (samples_per_class * num_classes)
    HLF_train = [None] * (samples_per_class * num_classes)
    return X_train, y_train, HLF_train
#-------------------------------------------------------------


def _check_inputs(data_dirs, observ_types):
    '''Helper Function - Makes sure that data_dirs, and observ_types are correctly formatted'''
    if (len(set(data_dirs)) != len(data_dirs)):
        raise ValueError("Cannot have duplicate directories %r" % data_dirs)
    for x in observ_types.values():
        if ("EvtId" in x):
            raise ValueError("Using EvtId in observ_types can result in skewed training results. Just don't.")



#--------------------SORTING UTILS--------------------------------
def maxLepPtEtaPhi(X, locs):
    for x in X:
        if (x[locs['isEle']] or x[locs["isMu"]]):
            return x[locs['Pt']], x[locs['Eta']], x[locs['Phi']]
        
def assertZerosBack(sort_slice, x, locs, sort_ascending):
    from numpy import inf
    sort_slice[np.all(x == 0.0, axis=1)] = inf if sort_ascending else -inf
    return sort_slice

def resolveMetric(s, locs, sort_ascending):
    if s in SORT_METRICS:
        return lambda x: assertZerosBack(SORT_METRICS[s](x, locs), x, locs, sort_ascending)
    else:
        raise ValueError("Unrecognized sorting metric %r" % s)


def _sortBy(x, sorts, sort_ascending):  
    if (sorts != None):
        for s in reversed(sorts):
            if (isinstance(s, int)):
                sort_slice = x[:, s]
            else:
                sort_slice = s(x)
            if (sort_ascending == True):
                x = x[sort_slice.argsort()]
            else:
                x = x[sort_slice.argsort()[::-1]]
    return x


def sort_numpy(x, sort_columns, sort_ascending, observ_types):
    '''Helper Function - pads the data and sorts it'''
    sort_locs = None
    assert not isinstance(sort_columns, string_types), "sort_columns improperly stored"
    if (sort_columns != None):
        if (True in [c in sort_columns for c in ["shuffle", "random"]]):
            np.random.shuffle(x)
        elif (not None in sort_columns):
            assert not False in [isinstance(s, string_types) for s in sort_columns], \
                "Type should be string got %s" % (",".join([str(type(s)) for s in sort_columns]))
            locs = {t: s for s, t in enumerate(observ_types)}
            sorts = [locs[s] if s in observ_types else resolveMetric(s, locs, sort_ascending)
                     for s in sort_columns]
            # KLUGE FIX
            x[x[:, locs["Energy"]] == 0] = 0.0
            # Sort
            x = _sortBy(x, sorts, sort_ascending)  

    return x
#------------------------------------------------------------------

#-------------------------SORTINGS---------------------------------
def MaxLepDeltaPhi(X, locs, mlpep=None):
    maxLepPt, maxLepEta, maxLepPhi = maxLepPtEtaPhi(X, locs) if isinstance(mlpep, type(None)) else mlpep
    out = maxLepPhi - X[:, locs["Phi"]]

    tooLarge = -2.0 * math.pi * (out > math.pi)
    tooSmall = 2.0 * math.pi * (out < -math.pi)
    out = out + tooLarge + tooSmall
    return out


def MaxLepDeltaEta(X, locs, mlpep=None):
    maxLepPt, maxLepEta, maxLepPhi = maxLepPtEtaPhi(X, locs) if isinstance(mlpep, type(None)) else mlpep
    return maxLepEta - X[:, locs["Eta"]]


def MaxLepDeltaR(X, locs, mlpep=None):
    mlpep = maxLepPtEtaPhi(X, locs) if isinstance(mlpep, type(None)) else mlpep
    return np.sqrt(MaxLepDeltaPhi(X, locs, mlpep) ** 2 + MaxLepDeltaEta(X, locs, mlpep) ** 2)


def MaxLepKt(X, locs):
    mlpep = maxLepPtEtaPhi(X, locs)
    maxLepPt, maxLepEta, maxLepPhi = mlpep
    return np.minimum(X[:, locs["Pt"]] ** 2, maxLepPt ** 2) * MaxLepDeltaR(X, locs, mlpep) ** 2


def MaxLepAntiKt(X, locs):
    mlpep = maxLepPtEtaPhi(X, locs)
    maxLepPt, maxLepEta, maxLepPhi = mlpep
    return np.minimum(X[:, locs["Pt"]] ** -2, maxLepPt ** -2) * MaxLepDeltaR(X, locs, mlpep) ** 2


SORT_METRICS = {f.__name__: f for f in
                [MaxLepDeltaPhi, MaxLepDeltaEta, MaxLepDeltaR, MaxLepKt, MaxLepAntiKt]}
#---------------------------------------------------------------------





import glob


def pandas_to_numpy(data_dirs, start, samples_per_class,
                    observ_types=DEFAULT_OBSERVS, sort_columns=None, sort_ascending=True, verbose=1):
    '''Builds a trainable (particle level) sorted and (event level) shuffled numpy array from directories of pandas .h5 files.
    
        :param data_dirs: 
            A list of pandas directories containing pandas .h5 files, tuples of ('label','dir'),
            or dictionary with .values() equal to such a list. The order indicates which
            files correspond to which output (i.e. the first directory corresponds to
            [1,0,...,0] and the second to [0,1,...,0], etc.). For dictionaries the 
            order defaults to the alphabetical order of the directory names.
        :param start:        Where to start reading (as if all of the files in a given directory are part of one long list)
        :param samples_per_class: The number of samples to read for each label. Every directory must have enough data starting
                            from 'start'.
        :param observ_types: The column headers for the data to be read from the panadas table. Also indicated the order of the columns.
        :param sort_columns: The columns to sort by, or special quantities including [MaxLepDeltaPhi,
                            MaxLepDeltaEta,MaxLepDeltaR,MaxLepKt,MaxLepAntiKt]
        :param sort_ascending: If True sort in ascending order, false decending  
        :returns: (X_train, Y_train, HFL_train) 
    '''
    if (isinstance(data_dirs, dict)): data_dirs = sorted(data_dirs.values(), key=lambda x: x.join(x.split("/")[::-1]))
    if (isinstance(data_dirs[0], tuple)): data_dirs = [x[1] for x in data_dirs]
    _check_inputs(data_dirs, observ_types)

    label_vecs = _gen_label_vecs(data_dirs)
    X_train, y_train, HLF_train = _initializeArrays(data_dirs, samples_per_class)
    X_train_index = 0

    y_train_start = 0
    for data_dir in data_dirs:
        files = glob.glob(os.path.abspath(data_dir) + "/*.h5")
        files.sort()
        samples_read, location = 0, 0

        sizesDict = get_sizes_meta_dict(data_dir)

        last_time = time.clock() - 1.0
        count,last_count = 0,0
        # Loop the files associated with the current label
        for f in files:
            file_total_events = size_from_meta(f, sizesDict=sizesDict)  # len(num_val_frame.index)
            if (file_total_events == None or file_total_events == 0):
                print("Skipping %r" % f)
                continue

            if (location + file_total_events <= start):
                location += file_total_events
                continue

            # Determine what row to start reading the num_val table which contains
            # information about how many rows there are for each entry
            file_start_read = start - location if start > location else 0

            # How many rows we will read from this table each corresponds to one entry
            samples_to_read = min(samples_per_class - samples_read, file_total_events - file_start_read)
            assert samples_to_read >= 0

            d = get_from_pandas(f, file_start_read=file_start_read,
                                       samples_to_read=samples_to_read,
                                       file_total_events=file_total_events,
                                       rows_per_event=DEFAULT_RPE,
                                       observ_types=observ_types)
            Particles, HLF = d["Particles"], d["HLF"]

            for s, (particles, hlf) in enumerate(zip(Particles, HLF)):
                # ----------pretty progress bar---------------
                
                if (verbose >= 1):
                    c = time.clock()
                    if (c > last_time + .25):
                        prog = X_train_index + s
                        percent = float(prog) / (samples_per_class * len(data_dirs))
                        sys.stdout.write('\r')
                        sys.stdout.write("[%-20s] %r/%r  %r(Event/sec)" % ('=' * int(20 * percent), prog,
                                                                           int(samples_per_class) * len(data_dirs),
                                                                           4 * (count-last_count)))
                        sys.stdout.flush()
                        #prev_sample = s
                        last_time = c
                        last_count = count

                count += 1
                # ------------------------------------------
                particles = sort_numpy(particles, sort_columns, sort_ascending, observ_types["Particles"])

                X_train[X_train_index + s] = particles
                HLF_train[X_train_index + s] = hlf

            X_train_index += samples_to_read

            location += file_total_events
            samples_read += samples_to_read
            if (samples_read >= samples_per_class):
                assert samples_read == samples_per_class
                break
        if (samples_read != samples_per_class):
            raise IOError(
                "Not enough data in %r to read in range(%r, %r)" % (data_dir, start, samples_per_class + start))

        # Generate the target data as vectors like [1,0,0], [0,1,0], [0,0,1]
        for i in range(samples_per_class):
            y_train[y_train_start + i] = label_vecs[data_dir]
        y_train_start += samples_per_class

    # Turn everything into numpy arrays and shuffle them just in case.
    # Although, we probably don't need to shuffle since keras shuffles by default.
    y_train = np.array(y_train)

    indices = np.arange(len(y_train))
    np.random.shuffle(indices)

    X_train = np.array(X_train)[indices]
    HLF_train = np.array(HLF_train)[indices]
    y_train = y_train[indices]

    return X_train, y_train, HLF_train

def splitsFromVal(v,n_samples):
    if(v == 0.0): return (n_samples,)
    if(v < 1.0):
        return (1.0-v,v)
    elif(isinstance(v, int) or v == int(v)):
        return (n_samples-int(v), int(v))
    else:
        raise ValueError("Cannot make fractional validation samples %r" % v)
        
    

def set_range_from_splits(splits, length):
    '''Takes in a tuple of splits and a length and returns a list of tuples with the starts and number of
        samples for each split'''
    if (True in [x < 0.0 for x in splits]):
        raise ValueError("Splits cannot be negative %r" % str(splits))
    are_static_vals = [(True if int(x) > 0 else False) for x in splits]
    if (True in are_static_vals):
        ratios = [s for s, a in zip(splits, are_static_vals) if (not a)]
        static_vals = [s for s, a in zip(splits, are_static_vals) if (a)]
        s = sum(static_vals)
        if (s > length):
            raise ValueError("Static values have sum %r exceeding given length %r" % (s, length))
        length -= s
    else:
        ratios = splits
    if (len(ratios) > 0 and np.isclose(sum(ratios), 1.0) == False):
        raise ValueError("Sum of splits %r must equal 1.0" % sum(ratios))

    nums = [int(s) if (a) else int(s * length) for s, a in zip(splits, are_static_vals)]
    out = []
    start = 0
    for n in nums:
        out.append((start, n))
        start += n
    return out


def strideFromTargetSize(rows_per_event, observ_types, num_classes, megabytes=100):
    '''Computes how large a stride is required to build a file with size megabytes'''
    megabytes_per_sample = sum([rows_per_event[key]*observ_types for key, in rows_per_event]) * 24.0 / (1000.0 * 1000.0)
    return int(megabytes/megabytes_per_sample)


def _checkDir(dir):
    out_dir = os.path.abspath(dir)
    if (not(os.path.exists(out_dir) and os.path.isdir(out_dir))):
        raise IOError("no such directory %r" % out_dir)
    return out_dir

def runAndStore():
    pass

def check_enough_data(sources, num_samples):
    for s in sources:
        files = glob.glob(os.path.abspath(s) + "/*.h5")
        tot = 0
        sizesDict = get_sizes_meta_dict(s)
        for f in files:
            tot += size_from_meta(f, sizesDict=sizesDict)
        if(tot < num_samples):
            raise IOError("Only %r samples in %r but requested %r" % (tot,s,num_samples))
    

def make_datasets(sources, output_dir, num_samples, size=1000,
                  num_processes=1, sort_on=None, sort_ascending=False,
                  v_split=0.0, force=False):
    '''Creates a data set in the output_dir folder with /train and /val subdirectories
    
        :param sources: a list of source directories of pandas .h5 files. Order matters; 
                        the first source corresponds to [1,0,..,0], the second to [0,1,..,0],etc.
        :type sources: list of str
        :param output_dir: the directory to output to
        :type output_dir: str
        :param num_samples: the number of samples to take for each class
        :type num_samples: int
        :param size: the number of samples to put in each file, or '<int>MB' (i.e '100MB')
                    corresponding to the target filesize
        :type size: int or str
        :param num_processes: The number of processes to use concurrently to build the dataset 
        :type num_processes: int 
        :param sort_on: The column or special value [MaxLepDeltaPhi,MaxLepDeltaEta,MaxLepDeltaR,MaxLepKt,MaxLepAntiKt] to sort on
        :type sort_on: str
        :param sort_ascending: whether to sort ascending or descending
        :type sort_ascending: bool
        :param v_split: the proportion of the total data to use for validation, 
                        or the total number of events to use (the rest goes to training)
        :type v_split: float or int
        
        
        
        '''
    sources = [_checkDir(s) for s in sources]

    check_enough_data(sources,num_samples)
    
    if(isinstance(size ,string_types)):
        if ("MB" in size):
            megabytes = int(re.search(r'\d+', size).group())
            stride = strideFromTargetSize(rows_per_event=DEFAULT_RPE, observ_types=DEFAULT_OBSERVS, megabytes=megabytes)
        else:
            stride = int(re.search(r'\d+', size).group())
    else:
        stride = size
    SNs = set_range_from_splits(splitsFromVal(v_split, num_samples), num_samples)

    if (not os.path.exists(output_dir)):
        os.mkdir(output_dir)
    jobs = []
    for i, sn in enumerate(SNs):
        folder = os.path.abspath(output_dir) + ("/train" if (i == 0) else '/val')
        if (force):
            try:
                shutil.rmtree(folder)
            except Exception:
                pass
        if (len(glob.glob(folder + "/*.h5")) != 0):
            raise IOError("directory %r is not empty use -f or --force to clear the directory first" % folder)

        if (not os.path.exists(folder)):
            os.mkdir(folder)
        order_of_mag = max(int(math.log(sn[1] / stride + 1, 10)), 3)
        end = sn[0] + sn[1]
        for j, start in enumerate(range(sn[0], end, stride)):
            samples_per_class = min(stride, end - start)
            kargs = {'data_dirs': sources, 'start': start, 'samples_per_class': samples_per_class,
                     'observ_types': DEFAULT_OBSERVS, 'sort_columns': [sort_on], 'sort_ascending': sort_ascending,
                     'verbose': 1}
            dest = os.path.abspath(folder + ("/%0" + str(order_of_mag) + "d.h5") % j)
            jobs.append((kargs, dest))

    def f(jobs):
        for kargs, dest in jobs:
            x = pandas_to_numpy(**kargs)
            h5f = h5py.File(dest, 'w')
            for D, key in zip(x, ["Particles", "Labels", "HLF"]):
                h5f.create_dataset(key, data=D)
            h5f.close()
            print("Done: %s/%s" % tuple(dest.split("/")[-2:]))

    num_processes = num_processes
    processes = []
    splits = [jobs[i::num_processes] for i in range(num_processes)]
    Ksamples_per_process = np.ceil(num_samples / num_processes)
    for i, sublist in enumerate(splits[1:]):
        print("Thread %r Started" % i)
        p = Process(target=f, args=sublist)
        processes.append(p)
        p.start()
        sleep(.001)
    try:
        f(splits[0])
    except Exception as e:
        for p in processes:
            p.terminate()
        raise e
    for p in processes:
        p.join()

def main(argv):
    parser = argparse.ArgumentParser(
        description='Convert ROOT data to numpy arrays stored as HDF5 for Machine Learning use.')
    parser.add_argument('sources', type=str, nargs='+')
    parser.add_argument('-o', '--output_dir', type=str, dest='output_dir', required=True)
    parser.add_argument('-n', '--num_samples', metavar='N', type=int, dest='num_samples', required=True)
    parser.add_argument('-p', '--num_processes', metavar='N', type=int, dest='num_processes', default=1,
                        help='How many processes to use concurrently.')
    parser.add_argument('-s', '--size', metavar='N', type=str, default='1000',
                        help='The number of samples per file to use. Can also indicate a target size in MB. An integer, or integer followed by MB (i.e 100MB)')
    parser.add_argument('-f', '--force', action='store_true',  default=False,
                        help='if true clean the output directory before starting, else throw an error')
    parser.add_argument('-v', '--validation_split', type=float, default=0.0, dest='v_split',
                        help='the proportion of samples that should be reserved for validation, or the number of samples_per_class that should be used')
    parser.add_argument('--sort_on', type=str, default=None, dest='sort_on',
                        help='The column or special value [MaxLepDeltaPhi,MaxLepDeltaEta,MaxLepDeltaR,MaxLepKt,MaxLepAntiKt] to sort on')
    parser.add_argument('--sort_ascending', action='store_true', default=False, dest='sort_ascending',
                        help='To sort ascending')
    parser.add_argument('--sort_descending', action='store_false', default=False, dest='sort_ascending',
                        help='To sort descending')
    
    try:
        args = parser.parse_args(argv)
    except Exception:
        parser.print_usage()
    make_datasets(args.sources, args.output_dir, args.num_samples, size=args.size, num_processes=args.num_processes,
                  sort_on=args.sort_on, sort_ascending=args.sort_ascending, v_split=args.v_split, force=args.force)
        

if __name__ == "__main__":
   main(sys.argv[1:])
