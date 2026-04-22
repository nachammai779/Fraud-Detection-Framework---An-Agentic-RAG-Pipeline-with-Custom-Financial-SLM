Read me for Household Survey Data

==============================================================================


This directory contains:
-sample SAS, Stata, and R programs to read the household survey data
-when using the data to subset to respondents, check for hsupresp==1
-the metadata folder has the data dictionary and code book
-the src folder has R code used to read the base CPS supplement and replicate weight files and prepare the csv of the analytic data sets.
-doc has documentation from census and also instrument.



                ./
                                contains analysis dataset as csv (in root of zip)
				

		/sample_read_programs
				sample programs showing how to read in data (SAS, Stata, and R)

		           
                /metadata
          
				metadata.csv (has codes/labels for analytic variables)
				The analytic variables were designed so that 'not in universe' (NIU) values are labeled -1.  Typically if a variable is the outcome variable of interest, then NIU should be subset out. 

                /src
                                R code to create csv from ascii file
					The main program is ProcessRawData.R (this program references ProcessRawDataVariableCreationFunction.R which contains the logic to create the analytic variables).
					The src folder also contains a subfolder called layout which contains SAS files, with infile information to read the fixed width file.
					Also this folder has raw data used to create the data under a folder called raw with ascii txt data.

             
		/doc
					This folder contains documentation on the survey from Census and a copy of the survey instrument.
                                     



Note: csv files of the analysis datasets use . as na or missing. So when reading the csv files, you should treat . as na in the read statement.  For example, in R the code would be:  hh2023<-read.csv("hh2023_analys.csv",na.strings=".").  
In the sample_read_programs folder there is also a R program that has an example of converting raw codes in the csv files to factors.

When comparing variables over time, use the appropirate definition based on the years you wish to investigate.  The metadata file indicates the valid years for each variable.