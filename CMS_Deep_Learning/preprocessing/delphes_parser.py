import os
import sys
if __package__ is None:
    #sys.path.append(os.path.realpath("../"))
    sys.path.append(os.path.realpath(__file__+"/../../../"))
    #print(os.path.realpath(__file__+"/../../../"))
import ROOT 
import numpy as np
import math
import time
import pandas as pd
from itertools import islice
import glob
import ntpath
import getopt
from CMS_Deep_Learning.storage.meta import msgpack_assertMeta


def DeltaRsq(A_Eta, A_Phi, B_Eta, B_Phi):
    '''Computes the 
        #Arguments
            #consider N = # of A, M = # of B
            A_Eta -- A numpy array of shape (N,) of all the Eta values of a certain
                        type of object in a given sample
            A_Phi -- A numpy array of shape (N,) of all the Phi values of a certain
                        type of object in a given sample
            B_Eta -- A numpy array of shape (M,) of all the Eta values of a certain
                        type of object in a given sample
            B_Phi -- A numpy array of shape (M,) of all the Phi values of a certain
                        type of object in a given sample
        #Returns
            A numpy ndarray of shape (N,M) containing the pairwise squared angular distances  
            between two sets of objects of types A and B
    '''

    B_Eta = B_Eta.reshape(1,B_Eta.shape[-1])
    B_Phi = B_Phi.reshape(1,B_Phi.shape[-1])

    A_Eta = A_Eta.reshape(A_Eta.shape[-1],1)
    A_Phi = A_Phi.reshape(A_Phi.shape[-1],1)

    #print(A_Eta.shape, B_Eta.shape)
    DeltaEta = A_Eta - B_Eta
    DeltaPhi = A_Phi - B_Phi
    
    tooLarge = -2.*math.pi*(DeltaPhi > math.pi)
    tooSmall = 2.*math.pi*(DeltaPhi < -math.pi)
    DeltaPhi = DeltaPhi + tooLarge + tooSmall    
    delRsq = DeltaEta*DeltaEta+DeltaPhi*DeltaPhi
    return delRsq

def trackMatch(prtEta, prtPhi, trkEta, trkPhi):
    '''Matches a reconstructed particle with its track
        #Arguments
            #consider N = # of particles, M = # of tracks
            prtEta -- A numpy array of shape (N,) of all the Eta values of a certain
                        type of reconstructed particle in a given sample
            prtPhi -- A numpy array of shape (N,) of all the Phi values of a certain
                        type of reconstructed particle in a given sample
            trkEta -- A numpy array of shape (M,) of all the Eta values of a track in 
                        a given sample
            trkPhi -- A numpy array of shape (M,) of all the trkPhi values of a track in 
                        a given sample
        #Returns
            A numpy array of shape (N,) containing the index of each track corresponding to each
            reconstruced particle.
    '''
    delRsq = DeltaRsq(prtEta, prtPhi, trkEta, trkPhi)
    index = np.argmin(delRsq, axis=1)
    return index


def Iso(A_Eta, A_Phi, A_Pt, B_Eta, B_Phi, to_ommit=None,maxdist=0.3):
    '''Computes the isolation between two object types
        #Arguments
            #consider N = # of particles in group A, M = # of particles in group B
            (A or B)_Eta --  numpy array with shape (N or M,) 
                                corresponding to the Eta values of the particles
            (A or B)_Phi --  numpy array with shape (N or M,) 
                                corresponding to the Phi values of the particles
            (A or B)_Pt --  numpy array with shape (N or M,) 
                                corresponding to the transverse momentum values of the particles
            maxdist -- The maximum cartesian distance between Eta and Phi to be included in the isolation
        #Returns
            The isolations of each particle in A w.r.t the particles in B
    '''
    DRsq = DeltaRsq(A_Eta, A_Phi, B_Eta, B_Phi)

    #Exclude particles in B that are too far away
    CloseTracks = DRsq < maxdist*maxdist
    DRsq = DRsq * CloseTracks

    out = np.sum(DRsq, axis=1, dtype='float64')/A_Pt
    return out

def getMaxPt_Eta_Phi(leaves_by_object,entry,obj, PT_ET_MET="PT"):
    '''Returns the PT, Eta and Phi corresponding to the particle of the highest PT in the object collection
        #Arguments
            dicts_by_object -- A dictionary keyed by object type containing dictionaries of arrays
                                    keyed by observable type. Arrays are expected to be prefilled with
                                    zeros
            leaves_by_object -- A dictionary keyed by object type, containing dictionaries of tuples
                                like (leaf, branch) keyed by observable type. Only valid ROOT
                                observables are used as keys. Each (leaf,branch) pair corresponds
                                to the leaf and branch of a ROOT observable.
            entry -- The entry to in the ROOT file to read from
        #Returns PT, Eta, Phi or if empty 0,0,0
    '''
    d = leaves_by_object[obj]
    for (leaf, branch) in d.values():
        branch.GetEntry(entry)
    n_values = d["Phi"][0].GetLen()
    l_PT = d[PT_ET_MET][0]
    l_Eta = d["Eta"][0]
    l_Phi = d["Phi"][0]
    max_PT, max_index = 0.0,-1
    # print(obj,n_values)
    for i in range(n_values):
        PT = l_PT.GetValue(i)
        if(PT > max_PT):
            max_PT, max_index = PT, i
    if(max_index == -1):
        return 0.0,0.0,0.0

    return max_PT, l_Eta.GetValue(max_index), l_Phi.GetValue(max_index)

def passJetCuts(entry, leaves_by_object, num_jets=2, PT_threshold=40.0):
    leaf,branch = leaves_by_object["Jet"]["PT"]
    branch.GetEntry(entry)
    n_values = leaf.GetLen()
    vals = [leaf.GetValue(i) > PT_threshold for i in range(n_values)]
    return sum(vals) >= num_jets

def passLeptonCuts(entry, leaves_by_object, num_leptons=1, PT_threshold=20.0):
    eleaf,branch = leaves_by_object["Electron"]["PT"]
    branch.GetEntry(entry)
    mleaf,branch = leaves_by_object["MuonTight"]["PT"]
    branch.GetEntry(entry)
    
    vals = [eleaf.GetValue(i) > PT_threshold for i in range(eleaf.GetLen())] +\
           [mleaf.GetValue(i) > PT_threshold for i in range(mleaf.GetLen())]
    return sum(vals) >= num_leptons


def fill_object(dicts_by_object,leaves_by_object,entry,new_entry, start_index,obj, PT_ET_MET, M, others, maxLepPT_Eta_Phi, METPT_Eta_Phi):
    '''Fills an object with values for a given entry
        #Arguments
            dicts_by_object -- A dictionary keyed by object type containing dictionaries of arrays
                                keyed by observable type. Arrays are expected to be prefilled with
                                zeros
            leaves_by_object -- A dictionary keyed by object type, containing dictionaries of tuples 
                                like (leaf, branch) keyed by observable type. Only valid ROOT 
                                observables are used as keys. Each (leaf,branch) pair corresponds
                                to the leaf and branch of a ROOT observable.
            entry -- The entry to in the ROOT file to read from
            new_entry -- The new entry number for the sample (Does not correspond to entry if samples are removed)
            start_index -- Where to start filling each array in the dictionary dicts_by_object[obj].
                            They should all have the same length since each array is a column in a table.
            obj -- The type of object we are filling
            PT_ET_MET -- The particluar flavor of transverse energy for this kind of object either 
                        ('PT',  'ET', 'MET')
            M -- The mass of this kind of object
            others -- Any ROOT observables unique to this kind of object that we should read
                                             
        #Returns 
            The number of values filled in for each column of our table
            
    '''
    d = leaves_by_object[obj]
    fill_dict = dicts_by_object[obj]
    for (leaf, branch) in d.values():
        branch.GetEntry(entry)
    n_values = d["Phi"][0].GetLen()
    # print(obj,n_values)

    #start_index = index_by_objects[obj]
    lv = ROOT.TLorentzVector()
    l_PT = d[PT_ET_MET][0]
    l_Eta = d["Eta"][0]
    l_Phi = d["Phi"][0]
    l_others = [(other, d[other][0]) for other in others]
    #lv_leaves = [d[ lorentz_vars[i] ][0] for i in range(lorentz_vars)]
    maxLepPT, maxLepEta, maxLepPhi = maxLepPT_Eta_Phi
    METPT, METEta, METPhi = METPT_Eta_Phi
    for i in range(n_values):
        index = start_index + i
        # print(obj,index)
        PT = l_PT.GetValue(i)
        Eta = l_Eta.GetValue(i)
        Phi = l_Phi.GetValue(i)
        lv.SetPtEtaPhiM(PT,Eta,Phi, M)
        fill_dict["Entry"][index] = new_entry
        fill_dict["E/c"][index] = lv.E()
        fill_dict["Px"][index] = lv.Px()
        fill_dict["Py"][index] = lv.Py()
        fill_dict["Pz"][index] = lv.Pz()
        fill_dict["PT_ET"][index] = PT
        fill_dict["Eta"][index] = Eta
        fill_dict["Phi"][index] = Phi

        MaxLepDeltaEta = maxLepEta - Eta
        MaxLepDeltaPhi = maxLepPhi - Phi

        tooLarge = -2.0 * math.pi * (MaxLepDeltaPhi > math.pi)
        tooSmall = 2.0 * math.pi * (MaxLepDeltaPhi < -math.pi)
        MaxLepDeltaPhi = MaxLepDeltaPhi + tooLarge + tooSmall

        METDeltaEta = maxLepEta - Eta
        METDeltaPhi = maxLepPhi - Phi

        tooLarge = -2.0 * math.pi * (METDeltaPhi > math.pi)
        tooSmall = 2.0 * math.pi * (METDeltaPhi < -math.pi)
        METDeltaPhi = METDeltaPhi + tooLarge + tooSmall

        maxLepDeltaRSqr = (MaxLepDeltaEta) ** 2 + (MaxLepDeltaPhi)**2
        fill_dict["MaxLepDeltaEta"][index] = MaxLepDeltaEta
        fill_dict["MaxLepDeltaPhi"][index] = MaxLepDeltaPhi
        fill_dict["MaxLepDeltaR"][index] = np.sqrt(maxLepDeltaRSqr)
        fill_dict["MaxLepKt"][index] = min(PT**2, maxLepPT**2) * maxLepDeltaRSqr
        fill_dict["MaxLepAntiKt"][index] = min(PT**-2, maxLepPT**-2) * maxLepDeltaRSqr
        METDeltaRSqr = (METDeltaEta)**2 + (METDeltaPhi)**2
        fill_dict["METDeltaEta"][index] = METDeltaEta
        fill_dict["METDeltaPhi"][index] = METDeltaPhi
        fill_dict["METDeltaR"][index] = np.sqrt(METDeltaRSqr)
        fill_dict["METKt"][index] = min(PT ** 2, METPT ** 2) * METDeltaRSqr
        fill_dict["METAntiKt"][index] = min(PT ** -2, METPT ** -2) * METDeltaRSqr

        for (other, l_other) in l_others:
            #if(obj == "EFlowTrack"): print(other, l_other.GetValue(i))
            fill_dict[other][index] = l_other.GetValue(i)
        # for OUTPUT_OBSERVS
    return n_values


def fill_jet(dicts_by_object, leaves_by_object, entry, new_entry, start_index):
    '''Fills an object with values for a given entry
        #Arguments
            dicts_by_object -- A dictionary keyed by object type containing dictionaries of arrays
                                keyed by observable type. Arrays are expected to be prefilled with
                                zeros
            leaves_by_object -- A dictionary keyed by object type, containing dictionaries of tuples 
                                like (leaf, branch) keyed by observable type. Only valid ROOT 
                                observables are used as keys. Each (leaf,branch) pair corresponds
                                to the leaf and branch of a ROOT observable.
            entry -- The entry to in the ROOT file to read from
            new_entry -- The new entry number for the sample (Does not correspond to entry if samples are removed)
            start_index -- Where to start filling each array in the dictionary dicts_by_object[obj].
                            They should all have the same length since each array is a column in a table.
        #Returns 
            The number of values filled in for each column of our table

    '''
    d = leaves_by_object['Jet']
    fill_dict = dicts_by_object['Jet']
    for (leaf, branch) in d.values():
        branch.GetEntry(entry)
    n_values = d["Phi"][0].GetLen()

    lv = ROOT.TLorentzVector()
    l_PT = d['PT'][0]
    l_Eta = d["Eta"][0]
    l_Phi = d["Phi"][0]
    l_mass = d["Mass"][0]
   
    for i in range(n_values):
        index = start_index + i
        PT = l_PT.GetValue(i)
        Eta = l_Eta.GetValue(i)
        Phi = l_Phi.GetValue(i)
        Mass = l_mass.GetValue(i)
        lv.SetPtEtaPhiM(PT, Eta, Phi, Mass)
        fill_dict["Entry"][index] = new_entry
        fill_dict["E/c"][index] = lv.E()
        fill_dict["Px"][index] = lv.Px()
        fill_dict["Py"][index] = lv.Py()
        fill_dict["Pz"][index] = lv.Pz()
        for key, (leaf,branch) in d.items():
            # print(leaf)
            fill_dict[key][index] = leaf.GetValue(i)
    return n_values

def fillTrackMatch(dicts_by_object,obj, trackIndicies, prtStart, trackStart):
    '''Fills an object with values for a given entry
        #Arguments
            dicts_by_object -- A dictionary keyed by object type containing dictionaries of arrays
                                keyed by observable type. Arrays are expected to be prefilled with
                                zeros
            obj -- The type of object we are matching with a track
            trackIndicies -- The result of trackMatch(). A numpy array of indicies corresponding to
                            tracks being matched to particles
            prtStart -- Where to start filling in X,Y,Z, and Dxy values for paricles matched to tracks
            trackStart -- Where to start reading track values from.
                #Note: We need to know where to start because we may not be filling or reading from
                        the beginning of each of our table columns.
                                             
        #Returns(void)
            
    '''
    l = dicts_by_object[obj]
    t = dicts_by_object["EFlowTrack"]
    lX = l["X"]
    lY = l["Y"]
    lZ = l["Z"]
    lDxy = l["Dxy"]
    tX = t["X"]
    tY = t["Y"]
    tZ = t["Z"]
    tDxy = t["Dxy"]
    for lepI, trkI in enumerate(trackIndicies):
        lepIndex = lepI + prtStart
        trkIndex = trkI + trackStart
        # print(obj, lepIndex, trkIndex, tX[trkIndex], tY[trkIndex], tZ[trkIndex])
        lX[lepIndex] = tX[trkIndex]
        lY[lepIndex] = tY[trkIndex]
        lZ[lepIndex] = tZ[trkIndex]
        lDxy[lepIndex] = tDxy[trkIndex]

    
def fillIso(dicts_by_object,obj, isoType,  obj_start,iso):
    '''Fills an object with values for a given entry
        #Arguments
            dicts_by_object -- A dictionary keyed by object type containing dictionaries of arrays
                                keyed by observable type. Arrays are expected to be prefilled with
                                zeros
            obj -- The type of object are running isolation on
            isoType -- The object type corresponding to the type of isolation we are running
            obj_start -- Where to start filling in isolation values
                 #Note: We need to know where to start because we may not be filling or reading from
                        the beginning of each of our table columns.
            iso -- The result of Iso(). A list of isolation values.
        #Returns(void)     
    '''
    isoArr = dicts_by_object[obj][isoType]
    # print(type(iso), iso)
    for i in range(len(iso)):
        isoArr[obj_start+i] = iso[i]
        
def fillEventChars(entry, new_entry, leaves_by_object,dicts_by_object, METPT_Eta_Phi,maxLepPT_Eta_Phi,maxJetPT_Eta_Phi):
    d = dicts_by_object["EventChars"]
    jetPT_l,jetPT_b= leaves_by_object["Jet"]["PT"]
    muonPhi_l,muonPhi_b= leaves_by_object["MuonTight"]["Phi"]
    elecPhi_l,elecPhi_b= leaves_by_object["Electron"]["Phi"]
    jetPT_b.GetEntry(entry)
    muonPhi_b.GetEntry(entry)
    elecPhi_b.GetEntry(entry)
    
    num_jets = jetPT_l.GetLen()
    num_muon = muonPhi_l.GetLen()
    num_elec = elecPhi_l.GetLen()
    
    HT = 0.0
    for i in range(num_jets):
        # print(jetPT_l.GetValue(i))
        HT += jetPT_l.GetValue(i)
        
    d['Entry'][new_entry] = new_entry
    d['HT'][new_entry] = HT
    d['JetMul'][new_entry] = num_jets
    d['ElectronMul'][new_entry] = num_elec
    d['MuonMul'][new_entry] = num_muon
    d['MET'][new_entry] = METPT_Eta_Phi[0]
    d['MaxLepPT'][new_entry] = maxLepPT_Eta_Phi[0]
    d['MaxJetPT'][new_entry] = maxJetPT_Eta_Phi[0]
    


def getEtaPhiPTasNumpy(dicts_by_object,obj, start, n_vals):
    '''Gets numpy arrays corresponding to all of the Eta, Phi, and Pt values for a given object type
            in a given sample. Here start and n_vals specifiy where the sample starts and how long it is. 
        #Arguments
            dicts_by_object -- A dictionary keyed by object type containing dictionaries of arrays
                                keyed by observable type. Arrays are expected to be prefilled with
                                zeros
            obj -- The type of object we are reading from to create our numpy arrays
            start -- where to start reading in that object
                #Note: We need to know where to start because we may not be filling or reading from
                        the beginning of each of our table columns.
            n_vals -- How many values to read.
        #Returns
            Eta, Phi, Pt -- numpy arrays    
    '''
    
    PT_ET = "PT_ET" if obj != "Jet" else "PT"
    d = dicts_by_object[obj]
    Eta =  np.array( d["Eta"][start:start+n_vals] )
    Phi =  np.array( d["Phi"][start:start+n_vals] )
    Pt =  np.array( d[PT_ET][start:start+n_vals] )
    return Eta, Phi, Pt 


#Masses for electrons and muons
mass_of_electron = np.float64(0.0005109989461) #eV/c
mass_of_muon = np.float64(0.1056583715) 

OBJECT_TYPES = ['Electron', 'MuonTight', 'Photon', 'MissingET', 'EFlowPhoton', 'EFlowNeutralHadron', 'EFlowTrack',              "Jet"]
PT_ET_TYPES  = ['PT',          'PT',       'PT',      'MET',        'ET',           'ET',               'PT',                   'PT']
EXTRA_FILLS  = [['Charge'], ['Charge'],     [],        [],     ['Ehad', 'Eem'],  ['Ehad', 'Eem'], ['Charge','X', 'Y', 'Z', 'Dxy'],[]]
MASSES =    [mass_of_electron, mass_of_muon, 0,        0,           0,                0,                 0,                        0]
TRACK_MATCH =   [True,        True,        False,    False,        False,           False,              False,                  False]
COMPUTE_ISO =   [True,        True,        True,     False,        True,           True,              False,                    False]
LEPTON_TYPES = ['Electron', 'MuonTight']


ROOT_OBSERVS =  ['PT', 'ET', 'MET', 'Eta', 'Phi', 'Charge', 'X', 'Y', 'Z', 'Dxy', 'Ehad', 'Eem']
OUTPUT_OBSERVS =  ['Entry','E/c', 'Px', 'Py', 'Pz', 'PT_ET','Eta', 'Phi',
                    "MaxLepDeltaEta", "MaxLepDeltaPhi",'MaxLepDeltaR', 'MaxLepKt', 'MaxLepAntiKt', "METDeltaEta","METDeltaPhi",'METDeltaR', 'METKt', 'METAntiKt',
                    'Charge', 'X', 'Y', 'Z', 'Dxy', 'Ehad', 'Eem', 'MuIso', 'EleIso','ChHadIso','NeuHadIso','GammaIso']
JET_OBSERVS =  ['PT','Eta', 'Phi','Mass', 'Flavor', 'FlavorAlgo', 'FlavorPhys', 'BTag', 'BTagAlgo', 'BTagPhys','TauTag',
                'Charge', 'EhadOverEem', 'NCharged', 'NNeutrals', 'Beta', 'BetaStar', 'MeanSqDeltaR', 'PTD',
                'NSubJetsTrimmed', 'NSubJetsPruned', 'NSubJetsSoftDropped']


EVENT_CHARS = ['Entry','MET','HT','MuonMul','ElectronMul','JetMul','MaxJetPT', 'MaxLepPT']

JET_OUTPUT_OBSERVS = ['Entry','E/c', 'Px', 'Py', 'Pz'] + JET_OBSERVS
ISO_TYPES = [('MuIso', 'MuonTight'), ('EleIso','Electron'), ('ChHadIso','EFlowTrack') ,('NeuHadIso','EFlowNeutralHadron'),('GammaIso','EFlowPhoton')]

def delphes_to_pandas(filepath, verbosity=1, fixedNum=None, requireLepton=True):
    start_time = time.clock()
    fileIN = ROOT.TFile.Open(filepath)
    tree = fileIN.Get("Delphes")
    if(fixedNum == None):
        n_entries=tree.GetEntries()
    else:
        n_entries = fixedNum
    # print(fileIN.summary())
    tree.SetCacheSize(30*1024*1024)

    #Get all the leaves that we need to read and their associated branches
    leaves_by_object = {}
    for obj in OBJECT_TYPES:
        leaves_by_object[obj] = {}
        OBSERVS = ROOT_OBSERVS if obj != "Jet" else JET_OBSERVS
        for observ in OBSERVS:
            leaf = tree.GetLeaf(obj + '.' + observ)
            if(isinstance(leaf,ROOT.TLeafElement)):
                leaves_by_object[obj][observ] = (leaf, leaf.GetBranch())
    # leaf = tree.GetLeaf('HepMCEvent.ProcessID')
    # leaves_by_object["HepMCEvent.ProcessID"] = (leaf, leaf.GetBranch())

    #Allocate the data for the tables by filling arrays with zeros
    dicts_by_object = {}
    dicts_by_object["NumValues"] = {}
    dicts_by_object["EventChars"] = {}
    for obj in OBJECT_TYPES:
        dicts_by_object[obj] = {}
        (leaf, branch) = leaves_by_object[obj]['Phi']
        total_values = 0

        #Loop over all the Phi values (since everything has Phi) and accumulate
        #   the total number of values for each object type
        for entry in range(n_entries):
            branch.GetEntry(entry)
            total_values += leaf.GetLen()

        #Fill arrays with zeros to avoid reallocating data later
        O_OBSERVS = OUTPUT_OBSERVS if obj != "Jet" else JET_OUTPUT_OBSERVS
        # print(obj, len(OBSERVS), )
        for observ in O_OBSERVS:
            dicts_by_object[obj][observ] = [0] * total_values
        dicts_by_object["NumValues"][obj] = [0] * n_entries
    for char in EVENT_CHARS:
        dicts_by_object["EventChars"][char] = [0]* n_entries
        


    index_by_objects = {o:0 for o in OBJECT_TYPES}
    last_time = time.clock()
    prev_entry = 0
    to_ommit = []
    cut_sample_count = 0
    new_entry = 0
    for entry in range(n_entries):

        #Make a pretty progress bar in the terminal
        if(verbosity > 0):
            c = time.clock() 
            if(c > last_time + .25):
                percent = float(entry)/float(n_entries)
                sys.stdout.write('\r')
                sys.stdout.write("[%-20s] %r/%r  %r(Entry/sec)" % ('='*int(20*percent), entry, int(n_entries), 4 * (entry-prev_entry)))
                sys.stdout.flush()
                last_time = c
                prev_entry = entry

        #Initialize some temporary helper variables
        number_by_object = {}
        Eta_Phi_PT_by_object = {}

        if((passLeptonCuts(entry,leaves_by_object) or not requireLepton) and passJetCuts(entry, leaves_by_object)):
            # Find the PT,Eta, and Phi for the leption with the highest PT, and for the MET
            maxLepPT_Eta_Phi = max([getMaxPt_Eta_Phi(leaves_by_object, entry, obj) for obj in LEPTON_TYPES], \
                                   key=lambda x: x[0])
            METPT_Eta_Phi = getMaxPt_Eta_Phi(leaves_by_object, entry,"MissingET", "MET")
            maxJetPT_Eta_Phi = getMaxPt_Eta_Phi(leaves_by_object, entry,"Jet", "PT")
            
            fillEventChars(entry, new_entry, leaves_by_object, dicts_by_object, METPT_Eta_Phi,maxLepPT_Eta_Phi,maxJetPT_Eta_Phi)

            #Fill each type of object with everything that is observable in the ROOT file for that object
            #   in addition to Energy and the three components of momentum
            for obj, PT_ET_type, mass, extra_fills in zip(OBJECT_TYPES, PT_ET_TYPES, MASSES, EXTRA_FILLS):
                start = index_by_objects[obj]
                if obj != "Jet":
                    n = fill_object(dicts_by_object,leaves_by_object,entry,new_entry, start, obj, PT_ET_type, mass, extra_fills, maxLepPT_Eta_Phi, METPT_Eta_Phi)
                else:
                    n = fill_jet(dicts_by_object,leaves_by_object,entry,new_entry, start)
                dicts_by_object["NumValues"][obj][new_entry] = n
                number_by_object[obj] = n
                Eta_Phi_PT_by_object[obj] = getEtaPhiPTasNumpy(dicts_by_object,obj, start, n)

            #Do Track matching for objects with TRACK_MATCH = True
            trkEta, trkPhi, dummy = Eta_Phi_PT_by_object["EFlowTrack"]
            start_tracks = index_by_objects["EFlowTrack"]
            for obj, ok in zip(OBJECT_TYPES, TRACK_MATCH):
                if(ok):
                    start = index_by_objects[obj]
                    Phi, Eta, PT = Eta_Phi_PT_by_object[obj]
                    matches = trackMatch(Phi, Eta, trkEta, trkPhi)
                    track_ommitions = matches.tolist()
                    to_ommit += [start_tracks + x for x in track_ommitions]
                    isoEta, isoPhi, isoPt = Eta_Phi_PT_by_object["EFlowTrack"]

                    #Omit info for repeat tracks, for Isolation calculation
                    sel = np.arange(len(isoEta))
                    sel = np.delete(sel, track_ommitions)
                    Eta_Phi_PT_by_object["EFlowTrack"] = isoEta[sel], isoPhi[sel], isoPt[sel]
                    fillTrackMatch(dicts_by_object,obj, matches, start, start_tracks)

            #Compute isolation
            for obj, ok in zip(OBJECT_TYPES, COMPUTE_ISO):
                start = index_by_objects[obj]
                if(ok):
                    objEta, objPhi, objPt = Eta_Phi_PT_by_object[obj]
                    for iso_type, iso_obj in ISO_TYPES:
                        isoEta, isoPhi, isoPt = Eta_Phi_PT_by_object[iso_obj]
                        iso_val = Iso(objEta, objPhi, objPt, isoEta, isoPhi)
                        iso_val = iso_val - 1.0 if obj == iso_obj else iso_val
                        fillIso(dicts_by_object,obj, iso_type,  start, iso_val)

            for obj in OBJECT_TYPES:
                index_by_objects[obj] += number_by_object[obj]
            new_entry += 1
        else:
            cut_sample_count +=1
    pandas_out = {}
    for obj,d in dicts_by_object.items():
        if(obj == "NumValues"):
            df = pd.DataFrame(d, columns=OBJECT_TYPES)
        elif(obj == "EventChars"):
            df = pd.DataFrame(d, columns=EVENT_CHARS)
        else:
            O_OBSERVS = OUTPUT_OBSERVS if obj != "Jet" else JET_OUTPUT_OBSERVS
            df = pd.DataFrame(d, columns=O_OBSERVS)
        pandas_out[obj] = df.loc[(df!=0.0).any(axis=1)]
    
    #Remove Tracks that correspond to Electrons and Muons
    df = pandas_out["EFlowTrack"]
    to_drop = df.iloc[to_ommit]
    to_subtract = to_drop[['Entry']].groupby('Entry').agg({'Entry':'count'})
    to_subtract = to_subtract.rename(columns={'Entry':'EFlowTrack'})
   
    #Update the numValues so that they are correct
    pandas_out["NumValues"] = pandas_out["NumValues"].sub(to_subtract,fill_value=0)

    #assert pandas_out["NumValues"]['EFlowTrack'].dtype == int, "NumValues is wrong dtype, %r" %  pandas_out["EFlowTrack"]['Entry'].dtype
    
    cleaned = df.drop(df.index[to_ommit]).reset_index(drop=True)
    pandas_out["EFlowTrack"] = cleaned

    if (verbosity > 0): print("ElapseTime: %.2f" % float(time.clock()-start_time))
    if (verbosity > 0): print("Converted: %r of %r Entries %0.3f%% ommited %0.3f%% retained" \
                              % (n_entries-cut_sample_count, n_entries, 100*float(cut_sample_count)/float(n_entries),100*float(n_entries-cut_sample_count)/float(n_entries) ))
    return pandas_out


#http://stackoverflow.com/questions/3678869/pythonic-way-to-combine-two-lists-in-an-alternating-fashion
def roundrobin(*iterables):
   "roundrobin('ABC', 'D', 'EF') --> A D E B F C"
   # Recipe credited to George Sakkis
   pending = len(iterables)
   nexts = cycle(iter(it).next for it in iterables)
   while pending:
      try:
         for next in nexts:
             yield next()
      except StopIteration:
         pending -= 1
         nexts = cycle(islice(nexts, pending))


def makeJobs(data_folder,
                storeType,
                pandas_folder ="/pandas/"):
    if(data_folder[-1] == "/"): data_folder = data_folder[0:-1]
    files = glob.glob(data_folder + "/*.root")
    store_dir = data_folder + pandas_folder
    print(store_dir)
    if not os.path.exists(store_dir): os.makedirs(store_dir)
    jobs = [ (f,  store_dir, storeType) for f in files]
    return jobs

def doJob(job, redo=False):
    f, store_dir, storeType = job
    try:
        return store(f, store_dir,rerun=redo,storeType=storeType)
    except Exception as e:
        print(e)
        print("Something weird happened when parsing %r." % f)
    return None




def store(filepath, outputdir, rerun=False, storeType="hdf5"):
    filename = os.path.splitext(ntpath.basename(filepath))[0]
    if(storeType == "hdf5"):
        out_file = outputdir + filename + ".h5"
        print(out_file)
        store = pd.HDFStore(out_file)
        keys = store.keys()
        #print("KEYS:", set(keys))
        # print("KEYS:", set(["/"+key for key in OBJECT_TYPES+["NumValues"]]))
        #print("KEYS:", set(keys)==set(["/"+key for key in OBJECT_TYPES+["NumValues"]]))
        existing,required  = set(keys),set(["/"+key for key in OBJECT_TYPES+["EventChars","NumValues"]])
        if(not existing.issuperset(required) or rerun):
            #print("OUT",out_file)
            try:
                frames = delphes_to_pandas(filepath)
            except Exception as e:
                print(e)
                print("Failed to parse file %r. File may be corrupted." % filepath)
                store.close()
                return 0
            try:
                for key,frame in frames.items():
                    store.put(key, frame, format='table')
            except Exception as e:
                print(e)
                print("Failed to write to HDFStore %r" % out_file)
                store.close()
                return 0
        num = len(store.get('NumValues').index)
        store.close()
    elif(storeType == "msgpack"):
        out_file = outputdir + filename + ".msg"
        # meta_out_file = outputdir + filename + ".meta"
        print(out_file)
        if(not os.path.exists(out_file) or rerun):
            try:
                frames = delphes_to_pandas(filepath)
            except Exception as e:
                print(e)
                print("Failed to parse file %r. File may be corrupted." % filepath)
                return 0
            try:
                pd.to_msgpack(out_file, frames)
            except Exception as e:
                print(e)
                print("Failed to write msgpack %r" % out_file)
                return 0
            # pd.to_msgpack(meta_out_file, meta_frames)
            meta_frames = msgpack_assertMeta(out_file, frames)
        else:
            meta_frames = msgpack_assertMeta(out_file)

        num = len(meta_frames["NumValues"].index)
        # elif(not os.path.exists(meta_out_file)):
        #     print(".meta file missing creating %r" % meta_out_file)
        #     frames = pd.read_msgpack(out_file)
        #     meta_frames = {"NumValues" : frames["NumValues"]}
        #     pd.to_msgpack(meta_out_file, meta_frames)
    else:
        raise ValueError("storeType %r not recognized" % storeType)
    return num, out_file

def main(data_dir, argv):
    from multiprocessing import Process
    from time import sleep
    # print(data_dir)
    storeType = "hdf5"
    redo = False
    num_samples = None
    num_processes = 1
    screwup_error = "python delphes_parser.py <input_dir>"
    try:
        opts, args = getopt.getopt(argv,'n:p:mrh')
        print(opts)
        print(args)
    except getopt.GetoptError:
        print(argv)
        # print(args)
        print screwup_error
        sys.exit(2)
  
    for opt, arg in opts:
      # print(opt, arg)
        if opt in ("-m", "--msg", "--msgpack"):
            storeType = "msgpack"
        elif opt in ('-h5', "--hdf", "--hdf5"):
            storeType = "hdf5"
        elif opt in ('-r', "--redo"):
            redo = True
        elif opt in ('-n', "--num_samples"):
            if(arg == ''): arg = None
            num_samples = int(arg)
        elif opt in ('-p', "--num_processes"):
            if(arg == ''): arg = None
            num_processes = int(arg)
    print(num_samples)
    print(storeType)
    pandas_folder = "/pandas_h5/" if storeType == "hdf5" else "/pandas_msg/"
    jobs = makeJobs(data_dir,storeType, pandas_folder=pandas_folder)

    def f(jobs ,samples_per_process,verbose=0 , i=0):
        samples_read = 0
        if (verbose >= 1): print("Parse process %r started." % i)
        for job in jobs:
            # ok = True
            out = doJob(job)
            if(not isinstance(out,tuple)):
                print("Something wrong with root file. Skipping...")
                continue
                # ok = False
            # else:

            samples_from_job, out_file = out
            try:
                store = pd.HDFStore(out_file)
                num_val_frame = store.get('/NumValues')
            except Exception as e:
                # ok = False
                print(e)
                print("Corrupted HDFStore. Skipping...")
                continue
            # if(ok):
            samples_read += samples_from_job
            print("Parsed %r of %r samples dedicated to process %r" % (samples_read, samples_per_process, i))
            if (samples_read >= samples_per_process):
                break


    processes = []
    # if (verbose >= 1): print("Starting  stating with %r/%r DataProcedures" % (len(dps) - len(unarchived), len(dps)))
    splits = [ jobs[i::num_processes] for i in range(num_processes)]
    samples_per_process = np.ceil(num_samples / num_processes)
        # np.array_split(jobs, num_processes)
    for i, sublist in enumerate(splits[1:]):
        print("Thread %r Started" % i)
        p = Process(target=f, args=(sublist,samples_per_process,1, i + 1))
        processes.append(p)
        p.start()
        sleep(.001)
    try:
        f(splits[0], samples_per_process, verbose=1)
    except:
        for p in processes:
            p.terminate()
    for p in processes:
        p.join()
    # for job in jobs:
    #     pandas_file = job[0]
    #     store = pd.HDFStore(pandas_file)

    # if False in [u.is_archived() for u in unarchived]:
    #     print("Batch Assert Failed")
    #     pass  # batchAssertArchived(dps, num_processes=num_processes)


    # samples_read = 0
    # for job in jobs:
    #     # print(job)
    #     samples_read += doJob(job, redo=redo)
    #     if(num_samples != None):
    #         print("Parsed %r of %r samples" %(samples_read, num_samples))
    #         if(samples_read >= num_samples):
    #             break
            




if __name__ == "__main__":

   main(sys.argv[1],sys.argv[2:])




# if __name__ == "__main__":
#     delphes_to_pandas("../data/ttbar_lepFilter_13TeV_147.root")


        
