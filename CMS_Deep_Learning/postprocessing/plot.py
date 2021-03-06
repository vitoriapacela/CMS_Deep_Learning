'''
metrics.py
Contains custom utilities for ploting and displaying training data.
Author: Danny Weitekamp
e-mail: dannyweitekamp@gmail.com
''' 

import matplotlib.pyplot as plt
import numpy as np
from .analysistools import *
from IPython.display import Image, display
from .metrics import get_roc_data
from .colors import resolveColors

def plot_history( histories, plotLoss=True, plotAccuracy=True, plotBest=True, title=None, acclims=None, useGrid=True, show=True):
    """ Plots an array of training histories against each other
        -input: [(String label, History hist, (optional) color), .... ]
        -Adopted from Jean-Roch Vlimant's Keras tutorial"""

    from keras.callbacks import History

    colors=[tuple(np.random.random(3)) for i in range(len(histories))]
    if(plotLoss):
        plt.figure(figsize=(10,10))
        plt.xlabel('Epoch', fontsize=16)
        plt.ylabel('loss', fontsize=16)
        if(title == None):
            plt.title('Training Error by Epoch', fontsize=20)
        else:
            plt.title(title, fontsize=20)
        for i, h in enumerate(histories):
            if(len(h) == 2):
                label,history = h
                color = colors[i]
            elif(len(h) == 3):
                label,history,color = h
            if(isinstance(history, History)):
                history = history.history
            l = label
            vl= label+" validation"
            if 'acc' in history:
                l+=' (best acc %2.4f)'% (max(history['acc']))
            if 'val_acc' in history:
                vl+=' (best acc %2.4f)'% (max(history['val_acc']))
            plt.plot(history['loss'],lw=2, ls='dashed', label=l, color=color)
            if 'val_loss' in history:
                plt.plot(history['val_loss'], lw=2, ls='solid', label=vl, color=color)
                
        plt.legend()
        plt.yscale('log')
        plt.grid(useGrid)
        if(show): plt.show()
        return plt
    
    if(plotAccuracy):
        plt.figure(figsize=(10,10))
        plt.xlabel('Epoch', fontsize=16)
        plt.ylabel('Accuracy', fontsize=16)
        if(title == None):
            plt.title('Validation Accuracy by Epoch', fontsize=20)
        else:
            plt.title(title,fontsize=20)
        for i, h in enumerate(histories):
            if(len(h) == 2):
                label,history = h
                color = colors[i]
            elif(len(h) == 3):
                label,history,color = h
            if(isinstance(history, History)):
                history = history.history
            if 'acc' in history:
                plt.plot(history['acc'], lw=2, ls='dashed', label=label+" training accuracy", color=color)
                if(plotBest):
                    best = max(history['acc'])
                    loc = history['acc'].index(best)
                    plt.scatter( loc, best, s=50, facecolors='none', edgecolors=color,
                                marker='x', linewidth=2.0, label=label+" best training accuracy = %0.4f" % best)
            if 'val_acc' in history:
                plt.plot(history['val_acc'], lw=2, ls='solid', label=label+" validation accuracy", color=color)
                if(plotBest):
                    best = max(history['val_acc'])
                    loc = history['val_acc'].index(best)
                    plt.scatter( loc, best, s=50, facecolors='none', edgecolors=color,
                                marker='o',linewidth=2.0, label=label+" best validation accuracy = %0.4f" % best)
        if(acclims != None):
             plt.ylim(acclims)
        plt.legend(loc='lower right')
        plt.grid(useGrid)
        if (show): plt.show()
        return plt


def print_accuracy( p, test_target):
    """ Prints the accuracy of a prediction array.
        -Taken from Jean-Roch Vlimant's Kreas tutorial"""
    p_cat = np.argmax(p,axis=1)
    print "Fraction of good prediction"
    print len(np.where( p_cat == test_target)[0])
    print len(np.where( p_cat == test_target )[0])/float(len(p_cat)),"%"
    
def print_accuracy_m( model, test_data, test_target):
    """ Prints the accuracy of a compiled model."""
    ##figure out the shape of the input expected
    #if hasattr('input_dim', model.layers[0]):
    p=model.predict(test_data)
    print_accuracy(p, test_target)


def plotMetricVsMetric(trials,metricX,metricY="val_acc",groupOn=None,constants={}, xlabel=None, ylabel=None, label="Trials", legend_label="", colors=None, shapes=None, alpha=.7, mode="max", verbose=0, verbose_errors=0, show=True):
    ''' Plots one metric that can be found in the records of a set of KerasTrials vs another (i.e. val_acc vs depth). 
        Asserts a one to one relationship incase of duplicate entries.
        
        :param trials: A list of trials to be used for the plot. This list will be culled down by specifying constants={"record" : value, ...}.
        :param metricX: The record entry to be used for the x-axis of the plot
        :param metricY: The record entry to be used for the y-axis of the plot
        :param groupOn: The record entry to group the data on to add a second explanitory variable
        :param constants: A dictionary of record values (i.e {"depth" : 2, ...}) that should be kept constant in the plot. For example 
                    if you only wanted to plot trials with a dropout of 0.0 you would do constants = {"dropout" : 0.0}.
                    Ideally you want to keep record values that are not being compared constant, to maintain a one-to-one relationship.
                    To be certain of this one-to-one relationship set mode="error".
        :param xlabel: The X label of the plot
        :param ylabel: The Y label of the plot
        :param label: How to label objects in the legend if groupOn=None
        :param legend_label: The title for the lengend
        :param colors: A list of colors to use to represent each group, defaults to CMS_Deep_Learning.utils.colors.colors_contrasting
        :param shapes: list of marker shapes to use in the graph, defualts to ['o','s','v', 'D', '^','*', '<', '>']
        :param alpha: The alpha value (opacity) for each point in the plot
        :param mode: How to assert a one-to-one relationship between the trials in each group. Either "max" or "min" which simply take the trial
                with the maximum or minimum 'metricY' value among conflicting trials. Alternately "error" throws an error if a one-to-one
                relationship cannot be resolved. The user can then edit the 'constants' argument to satisfy this relationship. 
                See CMS_Deep_Learning.analysistools.assertOneToOne for more information
        :param verbose: Whether or not to output extra information about the internals of the function for debugging.
        :param verbose_errors: Whether or not to print out longer summaries for conflicting trials if mode = "error".
            '''

    fig=plt.figure()
    ax1=fig.add_subplot(111)
    if(colors == None):
        from .colors import colors_contrasting1
        colors = colors_contrasting1
    if(shapes == None):
        shapes = ['o','s','v', 'D', '^','*', '<', '>']
    trials_by_group = {}
    if(groupOn != None):
        possibleValues = getMetricValues(trials,groupOn)
        #print(possibleValues)
        for v in possibleValues:
            trials_by_group[v] = findWithMetrics(trials, {groupOn:v})
    if(verbose == 1): print("POINTS:")
    i = 0
    for group,group_trials in (sorted(trials_by_group.iteritems()) if len(trials_by_group) > 0 else [(label,trials)]):
        group_trials = findWithMetrics(group_trials, constants)
        group_trials = assertOneToOne(group_trials, metricX,metricY=metricY, mode=mode, verbose_errors=verbose_errors)
        Xs = [ trial.get_from_record(metricX) for trial in group_trials]
        Ys = [trial.get_from_record(metricY) for trial in group_trials]
        #Sort lists together
        Xs, Ys = [list(x) for x in zip(*sorted(zip(Xs, Ys), key=lambda p: p[0]))]
        if(verbose == 1): print("%s: %r" % (group,zip(Xs, Ys)))
        c = colors[i % len(colors)] 
        j = (i +1) % len(colors)
        b = colors[j]
        s = shapes[i % len(shapes)]
        i += 1
        rects1 = plt.scatter(Xs, Ys,
                         #color='b',
                         #color=tuple(np.random.random(3)),
                         marker=s,
                         alpha =alpha,
                         s=50,
                         edgecolors=b,
                         color=c,
                         label=group)
        # plt.xticks(Xs)
    if(xlabel == None): xlabel = metricX
    if(ylabel == None): ylabel = metricY
    
    plt.xlabel(xlabel, fontsize=14)
    plt.ylabel(ylabel, fontsize=14)
    plt.title('%s vs %s' %(metricY, metricX), fontsize=18)
    legend = ax1.legend(title=legend_label, fontsize=12,loc='center left', bbox_to_anchor=(1, 0.5))
    #plt.legend()
    plt.setp(legend.get_title(),fontsize=14)
    #plt.tight_layout()
    if (show):plt.show()
    return plt

def plotEverything(trials, custom_objects={}):
    '''Plots all the information about a list of trials. For each trial: the model summary, a picture of the model and a plot of accuracy vs Epoch

    :param trials: A list of trials to plot
    :param custom_objects: in case your model includes layers that are not keras defaults, a dictionary of the layer classes keyed by their names
    '''

    #from keras.utils.visualize_util import plot

    if(not isinstance(trials, list)): trials = [trials]
    for b in trials:
        b.summary(showTraining=False,showValidation=False,showFit=True, showCompilation=False)
        labels = b.get_from_record("labels")
        if(labels == None): labels = b.get_from_record("lables")
        name = str(tuple(labels)) if(labels != None) else "Cannot Find Labels"
        model = b.get_model(custom_objects=custom_objects)
        history = b.get_history()
        plot_history([(name, history)], plotLoss = False)
        #dot = plot(model, to_file="model.png", show_shapes=True, show_layer_names=False)
        #image = Image("model.png")
        #display(image)
        try:
            from keras.utils.visualize_util import plot
            dot = plot(model, to_file="model.png", show_shapes=True, show_layer_names=False)
            image = Image("model.png")
            display(image)
        except Exception as e:
            print(e)


def plot_colors(colors, show_edges=False):
    '''Plots a list of colors with outlines taken from the same list

    '''
    fig, ax = plt.subplots(1)
    fig.set_size_inches((10, 10))

    # Show the whole color range
    for i in range(len(colors)):
        x = np.random.normal(loc=(i % 4) * 3, size=100)
        y = np.random.normal(loc=(i // 4) * 3, size=100)
        c = colors[i]
        j = (i * 3 + 4) % len(colors)
        b = colors[j] if show_edges else c

        ax.scatter(x, y, label=str(i), alpha=.7, edgecolor=b, s=60, facecolor=c, linewidth=1.0)
    return plt


def plot_table(rows, columns, cellText, rowColors=None, textSize=14, scale=1.5, title="",show=True):
    nrows, ncols = len(rows), len(columns)
    hcell, wcell = 0.005, 1.
    hpad, wpad = 0, 0    
    fig=plt.figure(figsize=(ncols*wcell+wpad, nrows*hcell+hpad))
    ax = fig.add_subplot(111)
    ax.axis('off')
    plt.title(title,loc="center",size=16)
    

    table = ax.table(cellText=cellText,
                          rowLabels=rows,
                          rowColours=rowColors,
                          colLabels=columns,
                          loc="bottom")
    table.set_fontsize(textSize)
    table.scale(scale, scale)
    if (show):plt.show()
    return plt


def plot_roc_curve(args=[], true_class_index=None, title="ROC_Curve", color_set="colors_contrasting1", show=True,
                   **kargs):
    '''Computes the ROC curve parameterization of the validation set and plots it. (or not if show=False). Requires (trial), or (Y,predictions) or (model,data), or (model,X,Y)
    
        .. note:: Mutliple plots can be made by passing in a list of dictionaries containing the relevent kargs.

        :param args: An alternative input method for multiple ROC curves. List of dictionaries of arguments for 
                    each curve.
        :param true_class_index: The index of the element of the predictions/labels that refers to the positive class
        :param title: The title of the plot
        :param color_set: A list of colors to use for each ROC.
        :param show: Whether or not to show the plot, can be useful if one only wants the parameterization data
        :param name: A name for use as a label in the plot
        :param *: Any argument available to :py:func:`CMS_Deep_Learning.postprocessing.metrics.get_roc_data` to get **ROC_data**,
                    and by extension any argument available to :py:func:`CMS_Deep_Learning.io.simple_grab` to get **Y**, **predictions**

        :returns: plt: the matplotlib handle, roc_dict:a list of dictionaries with ROC_data (tpr,fpr,thres,auc)

        '''
    from matplotlib import pyplot as plt
    inputs = args
    if (len(args) == 0):
        inputs = [kargs]

    colors = resolveColors(color_set)

    roc_dicts = []
    for i,inp in enumerate(inputs):
        name = inp.get('name', None)
        inp["true_class_index"] = true_class_index
        fpr, tpr, thres, roc_auc = get_roc_data(**inp)

        plt.figure()
        lw = 2
        plt.plot(fpr, tpr, color=colors[i], \
                 lw=lw, label='%r (AUC): %0.4f' % (name, roc_auc))
        roc_dicts.append({"name": name, "ROC_data": (fpr, tpr, thres, roc_auc)})

    plt.plot([0, 1], [0, 1], color='navy', lw=lw, linestyle='--')
    plt.xlim([-0.05, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title(title)
    plt.legend(loc="lower right")
    if (show): plt.show()
    return plt, roc_dicts


def plot_dual_roc(args=[], flipped=False, invertCont=False, title="",
                  true_class_index=None, color_set="colors_contrasting1", **kargs):
    '''Plots a roc curve or set of roc curves and its logscale counterpart
        
        :param args: An alternative input method for multiple ROC curves. List of dictionaries of arguments for 
                    each curve.
        :param flipped: T/F flip the axis
        :param invertCont: T/F use the inverse of contamination
        :param title: The title of the plot
        :param color_set: A list of colors to use for each ROC.
        :param name: A name for use as a label in the plot
        :param *: Any argument available to :py:func:`CMS_Deep_Learning.postprocessing.metrics.get_roc_data` to get **ROC_data**,
                    and by extension any argument available to :py:func:`CMS_Deep_Learning.io.simple_grab` to get **Y**, **predictions**
        
        :returns: plt: the matplotlib handle, roc_dict:a list of dictionaries with ROC_data (tpr,fpr,thres,auc) 
    '''
    from matplotlib import pyplot as plt
    from matplotlib import rc
    inputs = args
    if (len(args) == 0):
        inputs = [kargs]

    colors = resolveColors(color_set)

    rc('font', **{'family': 'sans-serif', 'sans-serif': ['Helvetica']})
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    roc_dicts = []
    for inp in inputs:
        inp["true_class_index"] = true_class_index
        inp["ROC_data"] = get_roc_data(**inp)
        roc_dicts.append({"name": inp.get('name', None), "ROC_data": inp["ROC_data"]})

    for k, (use_log, ax) in enumerate(zip([False, True], [ax1, ax2])):
        for i, inp in enumerate(sorted(inputs, key=lambda x: -x["ROC_data"][3])):
            name = inp.get('name', None)
            fpr, tpr, thres, roc_auc = inp["ROC_data"]

            if (invertCont):
                fpr = [min(1.0 / x, 40000.0) for x in fpr]

            if (flipped):
                ax.plot(tpr, fpr, color=colors[i],
                        lw=.7, label='%s (AUC): %0.4f' % (name, roc_auc))
            else:
                ax.plot(fpr, tpr, color=colors[i],
                        lw=.7, label='%s (AUC): %0.4f' % (name, roc_auc))

        ax.plot(np.linspace(0, 1, num=50), np.linspace(0, 1, num=50),
                color='navy', lw=.4, linestyle='--')

        if (flipped):
            if (use_log): ax.set_yscale("log")
            ax.set_xlim([0.0, 1.05])
            if (not invertCont): ax.set_ylim([-0.05, 1.05])
            ax.set_xlabel('signal efficiency (TPR)')
            if (invertCont):
                if (k == 0): ax.set_ylabel('1/(signal contamination) %s' % ("log-scale" if use_log else ""))
            else:
                if (k == 0): ax.set_ylabel('signal contamination %s (FPR)' % ("log-scale" if use_log else ""))
        else:
            if (use_log): ax.set_xscale("log")
            if (not invertCont): ax.set_xlim([-0.05, 1])
            ax.set_ylim([0.0, 1.05])
            if (k == 0): ax.set_ylabel('signal efficiency (TPR)')
            if (invertCont):
                ax.set_xlabel('1/(signal contamination) %s' % ("log-scale" if use_log else ""))
            else:
                ax.set_xlabel('signal contamination %s (FPR)' % ("log-scale" if use_log else ""))

    fig.suptitle(title, fontsize=18)
    ax.legend(loc='center left', bbox_to_anchor=(1, 0.5), prop={'size': 10})
    return plt, roc_dicts


def _expand_multi_vals(ys, binlabel, class_labels, normalize=False):
    out = {}
    if (True in [isinstance(y, dict) for y in ys]):
        key_set = list(set.union(*[set(d.keys()) for d in ys if isinstance(d, dict)]))
        ys = [d if isinstance(d, dict) else {k: 0.0 for k in key_set} for d in ys]

        prefix = binlabel + "_" if binlabel != "" else ""
        totals = [sum(y.values()) for y in ys]

        for k in key_set:
            class_label = class_labels[k] if class_labels != None else "class_" + str(k)
            y = [d[k] for d in ys]
            if (normalize): y = [float(v) / t for v, t in zip(y, totals)]
            out[prefix + class_label] = y
    else:
        out[binlabel] = ys
    return out


def plot_bins(bins,
              y_val="acc",
              min_samples=10,
              mode="bar",
              title='',
              xlabel='',
              ylabel='',
              class_labels=None,
              legendTitle=None,
              legendBelow=False,
              alpha=.8,
              colors=['b', 'g', 'r'],
              shapes=None,
              xlim=None,
              ylim=(0, 1.025),
              useGrid=True,
              log=False,
              stack=False,
              normalize=False,
              show=True):
    ''' Plots the output of CMS_Deep_Learning.utils.metrics.accVsEventChar

        :param bins: A list of dictionaries outputted by CMS_Deep_Learning.postprocessing.metrics.bin_metric_vs_char
                    or a dictionary of such lists keyed by a label for each binset.
        :param min_samples: The minumum number of samples that must be in a bin for it to be plotted.
        :param y_val: The y_value to plot 
        :param mode: "bar","scatter" or 'histo'
        :param title: The title of the plot
        :param xlabel: The xlabel of the plot
        :param ylabel: the ylabel of the plot
        :param class_labels: A list of labels to be shown in the legend. One for each set of bins.
        :param legendTitle: The title of the legend.
        :param legendBelow: Whether or not to put the legend below the graph
        :param alpha: The opacity of the plot.
        :param colors: the colors for each set of bins (see how matplotlib handles colors)
        :param shapes: the shapes of the markers for the graph
        :param xlim: a tuple (minX, maxX) that determines he x range of the view of the graph
        :param ylim: a tuple (minY, maxY) that determines he y range of the view of the graph 
        :param useGrid: if True then display a grid in the background of the graph
        :param args: An alternative input method for multiple ROC curves. List of dictionaries of arguments for 
                    each curve.
        :param true_class_index: The index of the element of the predictions/labels that refers to the positive class
        :param title: The title of the plot
        :param color_set: A list of colors to use for each ROC.
        :param show: Whether or not to show the plot, can be useful if one only wants the parameterization data


        :returns: plt: the matplotlib handle, roc_dict:a list of dictionaries with ROC_data (tpr,fpr,thres,auc)
        '''
    from matplotlib import pyplot as plt
    if (not isinstance(bins, dict)):
        bins = {"": bins}
    if (shapes == None):
        shapes = ['o', 's', 'v', 'D', '^', '*', '<', '>']
    if (not isinstance(colors, list)):
        colors = [colors]
    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111)
    if (useGrid):
        if (mode == "bar"):
            ax.yaxis.grid(True, which='major')
        else:
            ax.grid(True)
        ax.set_axisbelow(True)

    for i, (binlabel, bs) in enumerate(bins.items()):
        color = colors[i % len(colors)]
        label = binlabel  # binLabels[i] if binLabels != None and len(binLabels) > i else None
        xs = [b["min_bin_x"] for b in bs if (b["num_samples"] >= min_samples)]
        bot = np.array([0.0] * len(xs))
        widths = [b["max_bin_x"] - b["min_bin_x"] for b in bs if (b["num_samples"] >= min_samples)]

        ys = [b[y_val] for b in bs if (b["num_samples"] >= min_samples)]
        errors = None if not (y_val + "_error") in bs[0] \
            else [b[y_val + "_error"] for b in bs if (b["num_samples"] >= min_samples)]
        ys = _expand_multi_vals(ys, binlabel, class_labels, normalize)
        if errors != None:
            errors = _expand_multi_vals(errors,binlabel,class_labels)
        items = ys.items()
        if (mode == 'bar' or mode == 'histo'): items = sorted(items, key=lambda x: -np.average(x[1]))
        for j, (label, y) in enumerate(items):
            if (mode == "bar"):
                ax.bar(xs, y, width=widths, yerr=errors, color=colors[j % len(colors)], label=label, ecolor='k',
                       alpha=alpha, log=log)
            elif (mode == "histo"):
                if (stack):
                    ax.bar(xs, y, width=widths, yerr=errors, bottom=bot, color=colors[j % len(colors)], label=label,
                           ecolor='k', alpha=alpha, log=log, edgecolor="none", lw=0)
                else:
                    # Append points to beginning and end
                    _xs = [b["max_bin_x"] for b in bs if (b["num_samples"] >= min_samples)]
                    _xs = [bs[0]['min_bin_x']] + _xs + [_xs[-1]]
                    y = [0] + list(y) + [0]

                    ax.plot(_xs, y, ls='steps', color=colors[j % len(colors)], label=label, alpha=alpha)
                if (stack): bot += y
            else:
                s = shapes[i % len(colors)]
                ax.plot(xs, y, color=colors[j % len(colors)], label=label, marker=s, linestyle='None')
                ax.errorbar(xs, y, yerr=errors[label], color=colors[j % len(colors)], ecolor=colors[j % len(colors)],
                            alpha=alpha, fmt='',
                            linestyle='None')
                if (log): ax.set_yscale("log")

    ax.set_title(title, size=16)
    ax.set_xlabel(xlabel, size=14)
    ax.set_ylabel(ylabel, size=14)
    if (legendBelow):
        legend = ax.legend(title=legendTitle, fontsize=12, loc='upper center', bbox_to_anchor=(0.5, -0.15),
                           fancybox=True, ncol=2)
    else:
        legend = ax.legend(title=legendTitle, fontsize=12, loc='center left', bbox_to_anchor=(1, 0.5))

    if (legendTitle != None): plt.setp(legend.get_title(), fontsize=14)

    plt.ylim(ylim)
    plt.xlim(xlim)

    if (show): plt.show()
    return plt
