The script viz-perf-log-for-tableau.Rmd takes in a model log file, a Performance Monitor log file, and outputs a  CSV file that can be used in Tableau to visualize the performance of a model run. 
Then it generates some facet plots in R Markdown that can be used to visualize the performance data, as well. It doesn't look as nice but it will run quickly if you just want to see something fast.


This script expects you have two input  files the directory where this script is:
1. A model log file: pattern = "^tm2py_run.*\\.log$"
2. A Performance Monitor log file: pattern = "\\.blg$"
If there's already some files like that in there from another run you can move it to old_logs.

The script will convert the .blg file to a perfmon.csv file, read it in, and then parse the model log file. 

It will then align the data and write out one file for use in Tableau:


performance-log-for-tableau.csv


This can then be read into Tableau.


The script could use some cleanup because it writes out some intermediary files that aren't really necessary.
