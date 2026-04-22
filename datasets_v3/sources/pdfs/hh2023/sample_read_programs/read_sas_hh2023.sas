/* program to create sas data set */
* read in csv and bind labels and formats *;
* generate code to assign labels

* change path to where data is as needed;
LIBNAME _ALL_ CLEAR;

x 'cd C:\LOCAL DATA\{{local data}}\unbanked\downloads_2023\hh2023';
libname hh "C:\LOCAL DATA\{{local data}}\unbanked\downloads_2023\hh2023" ;



proc import datafile=".\sas_fmt\formatData.csv" out=hh.fmtdataset dbms=dlm replace;
   delimiter=",";
   getnames=yes;
   GUESSINGROWS=10000;
run;


PROC FORMAT library=hh.catalog CNTLIN=hh.fmtdataset;
RUN;

proc catalog catalog = hh.catalog;
contents;
run;
quit;


options  fmtsearch=(hh.catalog);

* how to turn off formats
*OPTIONS FMTSEARCH=( WORK LIBRARY) NOFMTERR NONOTES;





proc import datafile="hh2023_analys.csv" out=work.raw23 dbms=dlm replace;
   delimiter=",";
   getnames=yes;
run;


data hh.h2023;
	set work.raw23;
%include '.\sas_fmt\format_hh_survey.sas'; 

run;


PROC TABULATE DATA= hh.h2023 FORMAT=COMMA11.0;
      where hsupresp = 1;
      WEIGHT hsupwgtk ;
      CLASS hunbnk hryear4;
      VAR hsupresp;
      LABEL hsupresp='';
      TABLE hryear4,
                        all (all hunbnk)*
                              hsupresp*(SUM='Households (1000s)' rowpctsum='Percent'*F=COMMA5.1) / RTS=18;
RUN;
