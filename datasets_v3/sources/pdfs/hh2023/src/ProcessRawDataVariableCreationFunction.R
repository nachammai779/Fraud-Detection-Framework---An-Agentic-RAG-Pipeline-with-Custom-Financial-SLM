# contains function and logic to create derived analytic variables updated in 2019

createAnalyticHHData<-function(file)
{
library(sqldf)
library(plyr)


pp<-read.csv(file)
names(pp)<-tolower(names(pp))




##read in unbanked raw data
#latest<-read.csv("ubJUN2013PUBv2.csv")
#names_latest<-tolower(names(latest))
#rm(latest)
#gc()
#paste(names(latest),collapse="','")


names_latest=c( 'hrhhid','hrmonth','hryear4','hurespli','hufinal','filler','hetenure','hehousut','hetelhhd','hetelavl','hephoneo','hefaminc','hutypea',
'hutypb','hutypc','hwhhwgt','hrintsta','hrnumhou','hrhtype','hrmis','huinttyp','huprscnt','hrlonglk','hrhhid2','hwhhwtln','filler.1','hubus','hubusl1',
'hubusl2','hubusl3','hubusl4','gereg','gediv','filler.2','gestfips','filler.3','gtcbsa','gtco','gtcbsast','gtmetsta','gtindvpc','gtcbsasz','gtcsa','filler.4',
'filler.5','filler.6','perrp','filler.7','prtage','prtfage','pemaritl','pespouse','pesex','peafever','filler.8','peafnow','peeduca','ptdtrace','prdthsp','puchinhh',
'filler.9','pulineno','filler.10','prfamnum','prfamrel','prfamtyp','pehspnon','prmarsta','prpertyp','penatvty','pemntvty','pefntvty','prcitshp','prcitflg','prinuyer',
'puslfprx','pemlr','puwk','pubus1','pubus2ot','pubusck1','pubusck2','pubusck3','pubusck4','puretot','pudis','peret1','pudis1','pudis2','puabsot','pulay','peabsrsn',
'peabspdo','pemjot','pemjnum','pehrusl1','pehrusl2','pehrftpt','pehruslt','pehrwant','pehrrsn1','pehrrsn2','pehrrsn3','puhroff1','puhroff2','puhrot1','puhrot2',
'pehract1','pehract2','pehractt','pehravl','filler.11','puhrck1','puhrck2','puhrck3','puhrck4','puhrck5','puhrck6','puhrck7','puhrck12','pulaydt','pulay6m',
'pelayavl','pulayavr','pelaylk','pelaydur','pelayfto','pulayck1','pulayck2','pulayck3','pulk','pelkm1','pulkm2','pulkm3','pulkm4','pulkm5','pulkm6','pulkdk1',
'pulkdk2','pulkdk3','pulkdk4','pulkdk5','pulkdk6','pulkps1','pulkps2','pulkps3','pulkps4','pulkps5','pulkps6','pelkavl','pulkavr','pelkll1o','pelkll2o','pelklwo',
'pelkdur','pelkfto','pedwwnto','pedwrsn','pedwlko','pedwwk','pedw4wk','pedwlkwk','pedwavl','pedwavr','pudwck1','pudwck2','pudwck3','pudwck4','pudwck5','pejhwko',
'pujhdp1o','pejhrsn','pejhwant','pujhck1','pujhck2','prabsrea','prcivlf','prdisc','premphrs','prempnot','prexplf','prftlf','prhrusl','prjobsea','prpthrs',
'prptrea','prunedur','filler.12','pruntype','prwksch','prwkstat','prwntjob','pujhck3','pujhck4','pujhck5','puiodp1','puiodp2','puiodp3','peio1cow','puio1mfg',
'filler.13','filler.14','peio2cow','puio2mfg','filler.15','filler.16','puiock1','puiock2','puiock3','prioelg','pragna','prcow1','prcow2','prcowpg','prdtcow1',
'prdtcow2','prdtind1','prdtind2','prdtocc1','prdtocc2','premp','prmjind1','prmjind2','prmjocc1','prmjocc2','prmjocgr','prnagpws','prnagws','prsjmj','prerelg',
'peernuot','peernper','peernrt','peernhry','pternh1c','pternh2','pternh1o','pternhly','pthr','peernhro','pternwa','ptwk','prernmin','filler.17','ptern','ptern2',
'ptot','filler.18','peernwkp','peernlab','peerncov','penlfjh','penlfret','penlfact','punlfck1','punlfck2','peschenr','peschft','peschlvl','prnlfsch','pwfmwgt',
'pwlgwgt','pworwgt','pwsswgt','pwvetwgt','prchld','prnmchld','pxpdemp1','prwernal','prhernal','hxtenure','hxhousut','hxtelhhd','hxtelavl','hxphoneo','pxinusyr',
'pxrrp','filler.19','pxage','pxmaritl','pxspouse','pxsex','pxafwhn1','pxafnow','pxeduca','pxrace1','pxnatvty','pxmntvty','pxfntvty','pxnmemp1','pxhspnon','pxmlr',
'pxret1','pxabsrsn','pxabspdo','pxmjot','pxmjnum','pxhrusl1','pxhrusl2','pxhrftpt','pxhruslt','pxhrwant','pxhrrsn1','pxhrrsn2','pxhract1','pxhract2','pxhractt',
'pxhrrsn3','pxhravl','pxlayavl','pxlaylk','pxlaydur','pxlayfto','pxlkm1','pxlkavl','pxlkll1o','pxlkll2o','pxlklwo','pxlkdur','pxlkfto','pxdwwnto','pxdwrsn',
'pxdwlko','pxdwwk','pxdw4wk','pxdwlkwk','pxdwavl','pxdwavr','pxjhwko','pxjhrsn','pxjhwant','pxio1cow','pxio1icd','pxio1ocd','pxio2cow','pxio2icd','pxio2ocd',
'pxernuot','pxernper','pxernh1o','pxernhro','pxern','pxpdemp2','pxnmemp2','pxernwkp','pxernrt','pxernhry','pxernh2','pxernlab','pxerncov','pxnlfjh','pxnlfret',
'pxnlfact','pxschenr','pxschft','pxschlvl','qstnum','occurnum','pedipged','pehgcomp','pecyc','filler.20','filler.21','filler.22','pxdipged','pxhgcomp','pxcyc',
'filler.23','filler.24','filler.25','pwcmpwgt','peio1icd','ptio1ocd','peio2icd','ptio2ocd','primind1','primind2','peafwhn1','peafwhn2','peafwhn3','peafwhn4',
'pxafever','pepar2','pepar1','pepar2typ','pepar1typ','pecohab','pxpar2','pxpar1','pxpar2typ','pxpar1typ','pxcohab','pedisear','pedisrem','pedisphy',
'pedisdrs','pedisout','prdisflg','pxdisear','pxdiseye','pxdisrem','pxdisphy','pxdisdrs','pxdisout','hxfaminc','prdasian','pepdemp1','ptnmemp1','pepdemp2',
'ptnmemp2','pecert1','pecert2','pecert3','pxcert1','pxcert2','pxcert3','prsupint','heb10','heb15','heb20','heb40','heba10a','heba10b','heba10c','heba10d',
'heba10e','heba10f','heba15','heub10','heub15','heub50','heub55a2','heub55b1','heub55b2','heub55c','heub55d','heub55e','heub55f','heub55g1','heub55g2',
'heub55h','heub60','hepsuse10','hepuse10','hepsus20a','hepsus20b','hepsus20c','hepsus20d','hepsus20e','hepsus20f','hepsus20g','hepsus301','hepsus302',
'hepsus303','hepsus304','hepsus305','hepuse20a','hepuse20b','hepuse20c','hepuse20d','hepuse20e','hepuse20f','hepuse20g','henbmo10','henbmo201','henbmo202',
'henbmo203','henbmo204','henbmt10','henbmt201','henbmt202','henbmt203','henbmt204','henbcc10','henbcc20','hecnbpdl','hecnbpwn','hecnbtax','hecnbatl',
'hecnbrto','hebnpl10','hebnpl20','hebnpl301','hebnpl302','hebnpl303','hebnpl40','heccc10','hecsc10','hecal10','hechmln10','hecsl10','hecpl10','hecnbpl10',
'hecryp10','hecryp201','hecryp202','hecryp203','hecryp204','hecryp205','heh10','heh15','heh30','hxb40','hxba10a','hxba10b','hxba10c','hxba10d','hxba10e',
'hxba10f','hxba15','hxub10','hxub15','hxub50','hxub55a2','hxub55b1','hxub55b2','hxub55c','hxub55d','hxub55e','hxub55f','hxub55g1','hxub55g2','hxub55h',
'hxub60','hxpsuse10','hxpuse10','hxpsus20a','hxpsus20b','hxpsus20c','hxpsus20d','hxpsus20e','hxpsus20f','hxpsus20g','hxpsus301','hxpsus302','hxpsus303',
'hxpsus304','hxpsus305','hxpuse20a','hxpuse20b','hxpuse20c','hxpuse20d','hxpuse20e','hxpuse20f','hxpuse20g','hxnbmo10','hxnbmo201','hxnbmo202',
'hxnbmo203','hxnbmo204','hxnbmt10','hxnbmt201','hxnbmt202','hxnbmt203','hxnbmt204','hxnbcc10','hxnbcc20','hxcnbpdl','hxcnbpwn','hxcnbtax','hxcnbatl',
'hxcnbrto','hxbnpl10','hxbnpl20','hxbnpl301','hxbnpl302','hxbnpl303','hxbnpl40','hxccc10','hxcsc10','hxcal10','hxchmln10','hxcsl10','hxcpl10',
'hxcnbpl10','hxcryp10','hxcryp201','hxcryp202','hxcryp203','hxcryp204','hxcryp205','hxh10','hxh15','hxh30','hhsupwgt','pwsupwgt','hrhhid','hrmonth',
'hryear4','hurespli','hufinal','filler','hetenure','hehousut','hetelhhd','hetelavl','hephoneo','hefaminc','hutypea','hutypb','hutypc','hwhhwgt',
'hrintsta','hrnumhou','hrhtype','hrmis','huinttyp','huprscnt','hrlonglk','hrhhid2','hwhhwtln','filler.1','hubus','hubusl1','hubusl2','hubusl3',
'hubusl4','gereg','gediv','filler.2','gestfips','filler.3','gtcbsa','gtco','gtcbsast','gtmetsta','gtindvpc','gtcbsasz','gtcsa','filler.4',
'filler.5','filler.6','perrp','filler.7','prtage','prtfage','pemaritl','pespouse','pesex','peafever','filler.8','peafnow','peeduca','ptdtrace',
'prdthsp','puchinhh','filler.9','pulineno','filler.10','prfamnum','prfamrel','prfamtyp','pehspnon','prmarsta','prpertyp','penatvty','pemntvty',
'pefntvty','prcitshp','prcitflg','prinuyer','puslfprx','pemlr','puwk','pubus1','pubus2ot','pubusck1','pubusck2','pubusck3','pubusck4','puretot',
'pudis','peret1','pudis1','pudis2','puabsot','pulay','peabsrsn','peabspdo','pemjot','pemjnum','pehrusl1','pehrusl2','pehrftpt',
'pehruslt','pehrwant','pehrrsn1','pehrrsn2','pehrrsn3','puhroff1','puhroff2','puhrot1','puhrot2','pehract1','pehract2','pehractt','pehravl',
'filler.11','puhrck1','puhrck2','puhrck3','puhrck4','puhrck5','puhrck6','puhrck7','puhrck12','pulaydt','pulay6m','pelayavl','pulayavr',
'pelaylk','pelaydur','pelayfto','pulayck1','pulayck2','pulayck3','pulk','pelkm1','pulkm2','pulkm3','pulkm4','pulkm5','pulkm6','pulkdk1',
'pulkdk2','pulkdk3','pulkdk4','pulkdk5','pulkdk6','pulkps1','pulkps2','pulkps3','pulkps4','pulkps5','pulkps6','pelkavl','pulkavr','pelkll1o',
'pelkll2o','pelklwo','pelkdur','pelkfto','pedwwnto','pedwrsn','pedwlko','pedwwk','pedw4wk','pedwlkwk','pedwavl','pedwavr','pudwck1','pudwck2',
'pudwck3','pudwck4','pudwck5','pejhwko','pujhdp1o','pejhrsn','pejhwant','pujhck1','pujhck2','prabsrea','prcivlf','prdisc','premphrs','prempnot',
'prexplf','prftlf','prhrusl','prjobsea','prpthrs','prptrea','prunedur','filler.12','pruntype','prwksch','prwkstat','prwntjob','pujhck3',
'pujhck4','pujhck5','puiodp1','puiodp2','puiodp3','peio1cow','puio1mfg','filler.13','filler.14','peio2cow','puio2mfg','filler.15','filler.16',
'puiock1','puiock2','puiock3','prioelg','pragna','prcow1','prcow2','prcowpg','prdtcow1','prdtcow2','prdtind1','prdtind2','prdtocc1',
'prdtocc2','premp','prmjind1','prmjind2','prmjocc1','prmjocc2','prmjocgr','prnagpws','prnagws','prsjmj','prerelg','peernuot','peernper',
'peernrt','peernhry','pternh1c','pternh2','pternh1o','pternhly','pthr','peernhro','pternwa','ptwk','filler.17','filler.18','ptern',
'ptern2','ptot','filler.19','peernwkp','peernlab','peerncov','penlfjh','penlfret','penlfact','punlfck1','punlfck2','peschenr',
'peschft','peschlvl','prnlfsch','pwfmwgt','pwlgwgt','pworwgt','pwsswgt','pwvetwgt','prchld','prnmchld','pxpdemp1','prwernal',
'prhernal','hxtenure','hxhousut','hxtelhhd','hxtelavl','hxphoneo','pxinusyr','pxrrp','filler.20','pxage','pxmaritl','pxspouse',
'pxsex','pxafwhn1','pxafnow','pxeduca','pxrace1','pxnatvty','pxmntvty','pxfntvty','pxnmemp1','pxhspnon','pxmlr','pxret1','pxabsrsn',
'pxabspdo','pxmjot','pxmjnum','pxhrusl1','pxhrusl2','pxhrftpt','pxhruslt','pxhrwant','pxhrrsn1','pxhrrsn2','pxhract1','pxhract2',
'pxhractt','pxhrrsn3','pxhravl','pxlayavl','pxlaylk','pxlaydur','pxlayfto','pxlkm1','pxlkavl','pxlkll1o','pxlkll2o','pxlklwo',
'pxlkdur','pxlkfto','pxdwwnto','pxdwrsn','pxdwlko','pxdwwk','pxdw4wk','pxdwlkwk','pxdwavl','pxdwavr','pxjhwko','pxjhrsn','pxjhwant',
'pxio1cow','pxio1icd','pxio1ocd','pxio2cow','pxio2icd','pxio2ocd','pxernuot','pxernper','pxernh1o','pxernhro','pxern','pxpdemp2',
'pxnmemp2','pxernwkp','pxernrt','pxernhry','pxernh2','pxernlab','pxerncov','pxnlfjh','pxnlfret','pxnlfact','pxschenr','pxschft',
'pxschlvl','qstnum','occurnum','pedipged','pehgcomp','pecyc','filler.21','filler.22','filler.23','pxdipged','pxhgcomp','pxcyc',
'filler.24','filler.25','filler.26','pwcmpwgt','peio1icd','ptio1ocd','peio2icd','ptio2ocd','primind1','primind2','peafwhn1',
'peafwhn2','peafwhn3','peafwhn4','pxafever','pepar2','pepar1','pepar2typ','pepar1typ','pecohab','pxpar2','pxpar1','pxpar2typ',
'pxpar1typ','pxcohab','pedisear','pediseye','pedisrem','pedisphy','pedisdrs','pedisout','prdisflg','pxdisear','pxdiseye',
'pxdisrem','pxdisphy','pxdisdrs','pxdisout','hxfaminc','prdasian','pepdemp1','ptnmemp1','pepdemp2','ptnmemp2','pecert1',
'pecert2','pecert3','pxcert1','pxcert2','pxcert3','prsupint','heb10','heb15','heb20','heba10a','heba10b','heba10c','heba10d',
'heba10e','heba10f','heba15','heub10','heub15','heub50','heub55a2','heub55b1','heub55b2','heub55c','heub55d','heub55e','heub55f',
'heub55g1','heub55g2','heub55h','heub60','heub70','hepsuse10','hepuse10','hebuse20a','hebuse20b','hebuse20c','hebuse20d',
'hebuse20e','hebuse20f','hebuse20g','hepsus20a','hepsus20b','hepsus20c','hepsus20d','hepsus20e','hepsus20f','hepsus20g',
'hepsus301','hepsus302','hepsus303','hepsus304','hepsus305','hepuse20a','hepuse20b','hepuse20c','hepuse20d','hepuse20e',
'hepuse20f','hepuse20g','henbmo10','henbmo201','henbmo202','henbmo203','henbmo204','henbmt10','henbmt201','henbmt202','henbmt203',
'henbmt204','henbcc10','henbcc20','hecnbpdl','hecnbpwn','hecnbtax','hecnbatl','hecnbrto','heccc10','hecpl10','hecpl20','hecnbpl10',
'hecnbpl20','hele10','hele20a','hele20b','hele20c','hele20d','hele20e','hele301','hele302','hele401','hele402','hele403','hxba10a',
'hxba10b','hxba10c','hxba10d','hxba10e','hxba10f','hxba15','hxub10','hxub15','hxub50','hxub55a2','hxub55b1','hxub55b2','hxub55c','hxub55d',
'hxub55e','hxub55f','hxub55g1','hxub55g2','hxub55h','hxub60','hxub70','hxpsuse10','hxpuse10','hxbuse20a','hxbuse20b','hxbuse20c','hxbuse20d',
'hxbuse20e','hxbuse20f','hxbuse20g','hxpsus20a','hxpsus20b','hxpsus20c','hxpsus20d','hxpsus20e','hxpsus20f','hxpsus20g','hxpsus301','hxpsus302',
'hxpsus303','hxpsus304','hxpsus305','hxpuse20a','hxpuse20b','hxpuse20c','hxpuse20d','hxpuse20e','hxpuse20f','hxpuse20g','hxnbmo10','hxnbmo201',
'hxnbmo202','hxnbmo203','hxnbmo204','hxnbmt10','hxnbmt201','hxnbmt202','hxnbmt203','hxnbmt204','hxnbcc10','hxnbcc20','hxcnbpdl','hxcnbpwn','hxcnbtax',
'hxcnbatl','hxcnbrto','hxccc10','hxcpl10','hxcpl20','hxcnbpl10','hxcnbpl20','hxle10','hxle20a','hxle20b','hxle20c','hxle20d','hxle20e','hxle301',
'hxle302','hxle401','hxle402','hxle403','hhsupwgt','pwsupwgt','hulangcode','gcfip','gctcb','gctco','gctcs','peparent','puernh1c','peernh2','peernh1o',
'prernhly','prernwa','peern','puern2','pxparent','peio1ocd','peio2ocd','pelndad','pelnmom','pedadtyp','pemomtyp','pxlndad','pxlnmom','pxdadtyp',
'pxmomtyp','hep10','hepw10a','hepw10b','hepw10c','hepw10d','hepbuse','heub55a1','heub55g','henbmo15','henbmo16','henbbp10','henbbp15','henbcc15',
'henbrm10','henbrm15','henbp2p','heba10x','hebr10','hebr15','hea20','hea40','heca10','heca15','heca20','hes10','heh10','heh20','heh30','heh40','peb30',
'hxb20','hxp10','hxpw10a','hxpw10b','hxpw10c','hxpw10d','hxpbuse','hxub55a1','hxub55g','hxnbmo15','hxnbmo16','hxnbbp10','hxnbbp15','hxnbcc15','hxnbrm10','hxnbrm15',
'hxnbp2p','hxba10x','hxbr10','hxbr15','hxa20','hxa40','hxca10','hxca15','hxca20','hxs10','hxh10','hxh20','hxh30','hxh40','pxb30') 



old_names_latest=c('hrhhid','hrmonth','hryear4','hurespli','hufinal','huspnish','hetenure','hehousut','hetelhhd','hetelavl','hephoneo','hefaminc','hutypea','hutypb','hutypc','hwhhwgt',
'hrintsta','hrnumhou','hrhtype','hrmis','huinttyp','huprscnt','hrlonglk','hrhhid2','hwhhwtln','hubus','hubusl1','hubusl2','hubusl3','hubusl4','gereg','gediv','gestfips','gtcbsa','gtco',
'gtcbsast','gtmetsta','gtindvpc','gtcbsasz','gtcsa','perrp','peparent','prtage','prtfage','pemaritl','pespouse','pesex','peafever','peafnow','peeduca','ptdtrace','prdthsp','puchinhh','pulineno',
'prfamnum','prfamrel','prfamtyp','pehspnon','prmarsta','prpertyp','penatvty','pemntvty','pefntvty','prcitshp','prcitflg','prinusyr','puslfprx','pemlr','puwk','pubus1','pubus2ot','pubusck1','pubusck2',
'pubusck3','pubusck4','puretot','pudis','peret1','pudis1','pudis2','puabsot','pulay','peabsrsn','peabspdo','pemjot','pemjnum','pehrusl1','pehrusl2','pehrftpt','pehruslt','pehrwant','pehrrsn1','pehrrsn2',
'pehrrsn3','puhroff1','puhroff2','puhrot1','puhrot2','pehract1','pehract2','pehractt','pehravl','puhrck1','puhrck2','puhrck3','puhrck4','puhrck5','puhrck6','puhrck7','puhrck12','pulaydt','pulay6m','pelayavl',
'pulayavr','pelaylk','pelaydur','pelayfto','pulayck1','pulayck2','pulayck3','pulk','pelkm1','pulkm2','pulkm3','pulkm4','pulkm5','pulkm6','pulkdk1','pulkdk2','pulkdk3','pulkdk4','pulkdk5','pulkdk6','pulkps1',
'pulkps2','pulkps3','pulkps4','pulkps5','pulkps6','pelkavl','pulkavr','pelkll1o','pelkll2o','pelklwo','pelkdur','pelkfto','pedwwnto','pedwrsn','pedwlko','pedwwk','pedw4wk','pedwlkwk','pedwavl','pedwavr','pudwck1',
'pudwck2','pudwck3','pudwck4','pudwck5','pejhwko','pujhdp1o','pejhrsn','pejhwant','pujhck1','pujhck2','prabsrea','prcivlf','prdisc','premphrs','prempnot','prexplf','prftlf','prhrusl','prjobsea',
'prpthrs','prptrea','prunedur','pruntype','prwksch','prwkstat','prwntjob','pujhck3','pujhck4','pujhck5','puiodp1','puiodp2','puiodp3','peio1cow','puio1mfg','peio2cow','puio2mfg','puiock1',
'puiock2','puiock3','prioelg','pragna','prcow1','prcow2','prcowpg','prdtcow1','prdtcow2','prdtind1','prdtind2','prdtocc1','prdtocc2','premp','prmjind1','prmjind2','prmjocc1','prmjocc2',
'prmjocgr','prnagpws','prnagws','prsjmj','prerelg','peernuot','peernper','peernrt','peernhry','puernh1c','peernh2','peernh1o','prernhly','pthr','peernhro','prernwa','ptwk','peern','puern2',
'ptot','peernwkp','peernlab','peerncov','penlfjh','penlfret','penlfact','punlfck1','punlfck2','peschenr','peschft','peschlvl','prnlfsch','pwfmwgt','pwlgwgt','pworwgt','pwsswgt','pwvetwgt',
'prchld','prnmchld','pxpdemp1','prwernal','prhernal','hxtenure','hxhousut','hxtelhhd','hxtelavl','hxphoneo','pxinusyr','pxrrp','pxparent','pxage','pxmaritl','pxspouse','pxsex','pxafwhn1',
'pxafnow','pxeduca','pxrace1','pxnatvty','pxmntvty','pxfntvty','pxnmemp1','pxhspnon','pxmlr','pxret1','pxabsrsn','pxabspdo','pxmjot','pxmjnum','pxhrusl1','pxhrusl2','pxhrftpt','pxhruslt',
'pxhrwant','pxhrrsn1','pxhrrsn2','pxhract1','pxhract2','pxhractt','pxhrrsn3','pxhravl','pxlayavl','pxlaylk','pxlaydur','pxlayfto','pxlkm1','pxlkavl','pxlkll1o','pxlkll2o','pxlklwo','pxlkdur',
'pxlkfto','pxdwwnto','pxdwrsn','pxdwlko','pxdwwk','pxdw4wk','pxdwlkwk','pxdwavl','pxdwavr','pxjhwko','pxjhrsn','pxjhwant','pxio1cow','pxio1icd','pxio1ocd','pxio2cow','pxio2icd',
'pxio2ocd','pxernuot','pxernper','pxernh1o','pxernhro','pxern','pxpdemp2','pxnmemp2','pxernwkp','pxernrt','pxernhry','pxernh2','pxernlab','pxerncov','pxnlfjh','pxnlfret','pxnlfact',
'pxschenr','pxschft','pxschlvl','qstnum','occurnum','pedipged','pehgcomp','pecyc','pxdipged','pxhgcomp','pxcyc','pwcmpwgt','peio1icd','peio1ocd','peio2icd','peio2ocd','primind1',
'primind2','peafwhn1','peafwhn2','peafwhn3','peafwhn4','pxafever','pelndad','pelnmom','pedadtyp','pemomtyp','pecohab','pxlndad','pxlnmom','pxdadtyp','pxmomtyp','pxcohab','pedisear',
'pediseye','pedisrem','pedisphy','pedisdrs','pedisout','prdisflg','pxdisear','pxdiseye','pxdisrem','pxdisphy','pxdisdrs','pxdisout','hxfaminc','prdasian','pepdemp1','ptnmemp1',
'pepdemp2','ptnmemp2','pecert1','pecert2','pecert3','pxcert1','pxcert2','pxcert3'

,'hes1','hes1a','hes2','pes2a','pes2b','hes2e','hes2g1','hes2g2','hes2g3','hes2g4','hes2g5',
'hes2g6','hes2g7','hes2h','hes3','hes4','hes5a1','hes5a2','hes5b1','hes5b2','hes5c','hes5d','hes5e','hes5f','hes5g','hes5h','hes6','hes7','hes70','hes71','hes80a','hes80b'
,'hes80c','hes80d','hes80e','hes80f','hes80g','hes110','hes1111','hes1112','hes1113','hes1114','hes1115','hes1116','hes1121','hes1122','hes1123','hes1124','hes120','hes121',
'hes122','hes123','hes124','hes126','hes127','hes125','hes130','hes1351','hes1352','hes1353','hes140a','hes140b','hes140c','hes140d','hes140e','hes140x','hes141','hes150a',
'hes150b','hes150c','hes150d','hes150e','hes150f','hes150g','hes150h','hes150i','hes150x','hes1600a','hes1600b','hes1600c','hes1600d','hes1600e','hes1600f','hes1600g',
'hes162','hes163','hes164','hes170','hes1711','hes1712','hes1713','hes1714','hes1715','hes1716','hes1717','hes180','hes181','hes185','hes186','hes187','hhsupwgt',
'pwsupwgt','prsupint','hes101','hes131','hes132','hes133','hes134','hes151','hes160','hes161','hes182','hes183','hes184','hes18','hes23','hts21','hes24','hes28','hes17','hes31','hes20',
'hes427','hes49c','hes51g','pxgr6cor','pxms123','hes2c','hes2d1','hes2d2','hes2d3','hes2f','hes2i1','hes2i2','hes2i3','hes2i4','hes2i5','hes2i6','hes2i7','hes2i8','hes2i9','hes5a','hes5b',
'hes9','hes10','hes11','hes13b','hes14','hes15','hes16','hes19b','hes21','hes22','hes24b','hes25','hes26','hes27','hes28b','hes29','hes30','hes33','hes34','hes35','hes36','hes37','hes38',
'hes38b','hes38c','hes39','hes40','hes41','hes421','hes422','hes423','hes424','hes425','hes426','hes42b','hes43','hes44','hes451','hes452','hes453','hes454','hes455','hes456','hes457',
'hes458','hes45b1','hes45b2','hes45b3','hes45b4','hes45b5','hes45b6','hes45b7','hes45b8','hes45b9','hes46','hes47','hes48','hes49a','hes49b','hes49d','hes49e','hes49f','hes49g',
'hes49h','hes49i','hes49j','hes49k','hes50a','hes50b','hes50c','hes50d','hes50e','hes50f','hes50g','hes50h','hes50i','hes50j','hes50k','hes51a','hes51b','hes51c','hes51d','hes51e',
'hes51f','hes51h','hes51i','hes51j','hes51k')

names_latest=unique(names_latest)

oldvars=c( 'pxgr6cor','pxms123','hes2c','hes2d1','hes2d2','hes2d3','hes2f','hes2g4','hes2i1','hes2i2','hes2i3','hes2i4','hes2i5','hes2i6','hes2i7','hes2i8','hes2i9','hes5a','hes5b','hes9','hes10','hes11','hes13b','hes14','hes15','hes16','hes19b','hes20','hes21','hes22','hes24b','hes25','hes26','hes27','hes28b','hes29','hes30','hes31','hes33','hes34','hes35','hes36','hes37','hes38','hes38b','hes38c','hes39','hes40','hes41','hes421','hes422','hes423','hes424','hes425','hes426','hes427','hes42b','hes43','hes44','hes451','hes452','hes453','hes454','hes455','hes456','hes457','hes458','hes45b1','hes45b2','hes45b3','hes45b4','hes45b5','hes45b6','hes45b7','hes45b8','hes45b9','hes46','hes47','hes48','hes49a','hes49b','hes49c','hes49d','hes49e','hes49f','hes49g','hes49h','hes49i','hes49j','hes49k','hes50a','hes50b','hes50c','hes50d','hes50e','hes50f','hes50g','hes50h','hes50i','hes50j','hes50k','hes51a','hes51b','hes51c','hes51d','hes51e','hes51f','hes51g','hes51h','hes51i','hes51j','hes51k')

oldv2=old_names_latest[!old_names_latest %in% names_latest]


oldvars=unique(c(oldvars,oldv2))

##rename  gcfips to gestfips, hulangcode to huspnish, prinuer to prinusyr
#names(pp)[grep("hulang",names(pp))]<-"huspnish"
names(pp)[grep("gcfip",names(pp))]<-"gestfips"
names(pp)[grep("prinuyer",names(pp))]<-"prinusyr"
names(pp)[grep("gctco",names(pp))]<-"gtco"
names(pp)[grep("gctcb",names(pp))]<-"gtcbsa"
names(pp)[grep("peage",names(pp))]<-"prtage"
names(pp)[grep("hufaminc",names(pp))]<-"hefaminc"
names(pp)[grep("hus2e",names(pp))]<-"hes2e"


names_latest=names_latest[!grepl('px.*',names_latest)]

# missing variables to older surveys
pp[names_latest[!names_latest %in% names(pp)]]<-NA


# old questions not in future surveys to set missing
if (!c('hes18') %in% names(pp)) {print(1); pp$hes18<-NA}
if (!c('hes23') %in% names(pp)) {print(1); pp$hes23<-NA}
if (!c('hts21') %in% names(pp)) {print(1); pp$hts21<-NA}
if (!c('hes24') %in% names(pp)) {print(1); pp$hes24<-NA}
if (!c('hes28') %in% names(pp)) {print(1); pp$hes28<-NA}
if (!c('hes17') %in% names(pp)) {print(1); pp$hes17<-NA}
if (!c('hes31') %in% names(pp)) {print(1); pp$hes31<-NA}

if (!c('hes20') %in% names(pp)) {print(1); pp$hes20<-NA}
if (!c('hes427') %in% names(pp)) {print(1); pp$hes427<-NA}

if (!c('hes49c') %in% names(pp)) {print(1); pp$hes49c<-NA}

if (!c('hes51g') %in% names(pp)) {print(1); pp$hes51g<-NA}



for (i in 1:length(oldvars)) { if (!oldvars[i] %in% names(pp)) {print(oldvars[i]); pp[oldvars[i]]<-NA} }

# old 09/11 questions to retain in multiyear

if (!c('hes12') %in% names(pp)) {print(1); pp$hes12<-NA}
if (!c('hes8') %in% names(pp)) {print(1); pp$hes8<-NA}
if (!c('hes19') %in% names(pp)) {print(1); pp$hes19<-NA}
if (!c('hes22') %in% names(pp)) {print(1); pp$hes22<-NA}
if (!c('hes25') %in% names(pp)) {print(1); pp$hes25<-NA}
if (!c('hes29') %in% names(pp)) {print(1); pp$hes29<-NA}
if (!c('hes5') %in% names(pp)) {print(1); pp$hes5<-NA}
if (!c('hes13') %in% names(pp)) {print(1); pp$hes13<-NA}
if (!c('hes19') %in% names(pp)) {print(1); pp$hes19<-NA}
if (!c('hes18') %in% names(pp)) {print(1); pp$hes18<-NA}
if (!c('hes24') %in% names(pp)) {print(1); pp$hes24<-NA}
if (!c('hes28') %in% names(pp)) {print(1); pp$hes28<-NA}
if (!c('hes32') %in% names(pp)) {print(1); pp$hes32<-NA}
if (!c('hes37') %in% names(pp)) {print(1); pp$hes37<-NA}
if (!c('hts12') %in% names(pp)) {print(1); pp$hts12<-NA}
if (!c('hts17') %in% names(pp)) {print(1); pp$hts17<-NA}
if (!c('hts23') %in% names(pp)) {print(1); pp$hts23<-NA}

#max pes2a


print(names(pp))
pp=pp[,!grepl('filler',names(pp))]


imp_flags=unique(pp[,grepl('qstnum|perrp|hxp|hxb|hxs|hxt|pxs|hxu|hxu|hxb|hxn|hxl|hxc|hxp',names(pp))])
pp=pp[,!grepl('hxp|hxb|hxs|hxt',names(pp))]
#}


print(names(imp_flags))


print('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
print(names(pp))


pp=sqldf('select a.*,
case when hryear4-prtage>=1982 and  hryear4-prtage<=2000 and pwsswgt>0  then 1 else 0 end pmill,
case when pwsswgt>0 then case 
				when perrp in (4,5,7,8,9,13,15,17)   then 1
                        when  hrhtype=9  then 1 
     		     		when perrp in (1,2,3) and hrhtype in (1,2) then 2 
                 		when perrp in (1,2,3) and  hrhtype=9 and pemaritl in (1,2) then 2 
                		 when perrp in (1,2,3) and hrhtype in (3,4,5) then 3 else 4 end else 0 end plivstat,


case when hryear4-prtage>=1982 and  hryear4-prtage<=2000 and pwsswgt>0  then 
case 
		     when perrp in (4,5,7,8,9,13,15,17)   then 1
                 when  hrhtype=9  then 1 
     		     when perrp in (1,2,3) and hrhtype in (1,2) then 2 
                 when perrp in (1,2,3) and  hrhtype=9 and pemaritl in (1,2) then 2 
                 when perrp in (1,2,3) and hrhtype in (3,4,5) then 3 else 4 end else 0 end plivstat_mill

from pp a')


##create roll ups for children vars and hh bnk type from person level data
hh_variables_from_multiperson_data<-sqldf('select 
 qstnum,
 sum (case when prtage >= 0 and prtage <= 15 then 1 else 0 end) hagele15,
 sum (case when prtage >= 0 and prtage <= 16 then 1 else 0 end) hagele16,
 sum (case when prtage >= 0 and prtage <= 17 then 1 else 0 end) hagele17,

 sum (case when prtage >= 0 and prtage <= 18 then 1 else 0 end)  hagele18 ,

 sum (case when prtage >= 18 and prtage <= 150 then 1 else 0 end) hagege18,
 sum (case when prtage >= 16 and prtage <= 150 then 1 else 0 end)  hagege16,

 sum (case when prtage >= 15 and prtage <= 17 then 1 else 0 end)  hagege15_17,
 sum (case when prtage >= 15 and prtage <= 18 then 1 else 0 end)  hagege15_18,

 sum (case when prtage >= 18 and prtage <= 24 then 1 else 0 end)  hagege18_24,

 max (case when hryear4=2009 then null when hryear4<2019 and hes2=2 then 1  when hryear4>=2019 and (peb30=0 or heb20=2)  then 1 else 0 end) unbnk_yn,
 max (case when (hryear4=2009 or hryear4>=2019) then null when hryear4<2019 and pes2b in (1,3) then 1 else 0 end) ptypchk_yn,
 max (case when (hryear4=2009 or hryear4>=2019) then null when hryear4<2019 and pes2b in (2,3) then 1 else 0 end) ptypsav_yn,
 max (case when (hryear4=2009 or hryear4>=2019) then null when hes2 = 1 and (pes2a in (-2,-3,-9) or pes2b in (4,-2,-3,-9)) then 1 else 0 end) ptypunk_yn,
  count(*) pnum,

sum(case when prfamrel!=0 and pehruslt=-4 then pehractt when prfamrel!=0 then  pehruslt end ) p_hrs_wrk,
sum(case when prfamrel!=0 then 0 when prtage>65 then 0 when  pehruslt=-4 then pehractt when prftlf=1 then 40  when  pehruslt>0 then pehruslt else 25 end ) p_hrs_wrk2,

sum(prernwa) p_weekly_earn,

sum(case when hryear4=2009 then null when hryear4-prtage>=1982 and  hryear4-prtage<=2000  then 1 else 0 end) pnum_mill,
sum(case when hryear4=2009 then null 
	   when hryear4<2019 and hryear4-prtage>=1982 and  hryear4-prtage<=2000  and pes2a=1  then 1
         when hryear4>=2019 and hryear4-prtage>=1982 and  hryear4-prtage<=2000  and peb30=1 then 1
 else 0 end) pnum_mill_bnk,
sum(case when hryear4=2009 then null when hryear4<2019 and hryear4-prtage>=1982 and  hryear4-prtage<=2000  and (pes2a=0 or hes2=2)  then 1 
when hryear4>=2019 and hryear4-prtage>=1982 and  hryear4-prtage<=2000  and (peb30=0 or heb20=2) then 1
else 0 end) pnum_mill_unbnk,
sum(case when (hryear4=2009 or hryear4>=2019) then null 
when hryear4<2019 and hryear4-prtage>=1982 and  hryear4-prtage<=2000  and pes2a not in (0,1) and hes2!=2  then 1 else 0 end) pnum_mill_unk,


 sum(case when hryear4=2009 then null when hryear4<2019 and prtage>=0 and prtage<15 and pes2a=1  then 1  when hryear4>=2019 and prtage>=0 and prtage<15 and peb30=1 then 1  else 0 end) pnumlt15bnk,
 sum(case when hryear4=2009 then null when hryear4<2019 and prtage>=0 and prtage<15 and (pes2a=0 or hes2=2)   then 1
when hryear4>=2019 and prtage>=0 and prtage<15 and (peb30=0 or heb20=2)   then 1
 else 0 end) pnumlt15unbnk,
 sum(case when hryear4=2009 then null when hryear4<2019 and prtage>=0 and prtage<15 and pes2a not in (0,1) and hes2!=2  then 1 else 0 end) pnumlt15unk,

 sum(case when hryear4=2009 then null when hryear4<2019 and prtage>=15 and prtage<=17 and pes2a=1 then 1 
when hryear4>=2019 and prtage>=15 and prtage<=17 and peb30=1 then 1  else 0 end) pnum15_17bnk,

 max (case when (hryear4=2009 or hryear4>=2019) then null when hryear4<2019 and prtage>=15 and prtage<=17 and pes2b in (1,3) then 1 else 0 end) pnum15_17chk,
 max (case when (hryear4=2009 or hryear4>=2019) then null when hryear4<2019 and prtage>=15 and prtage<=17 and pes2b in (2,3) then 1 else 0 end) pnum15_17sav,


 sum(case when hryear4=2009 then null when hryear4<2019 and prtage>=15 and prtage<=17 and  (pes2a=0 or hes2=2)  then 1 
 when hryear4>=2019 and prtage>=15 and prtage<=17 and  (peb30=0 or heb20=2)  then 1
else 0 end) pnum15_17unbnk,
 sum(case when (hryear4=2009 or hryear4>=2019) then null when hryear4<2019 and prtage>=15 and prtage<=17 and pes2a not in (0,1) and hes2!=2  then 1 else 0 end) pnum15_17unk,

 sum(case when hryear4=2009 then null when hryear4<2019 and prtage>=18 and prtage<=150 and pes2a=1 then 1 
when hryear4>=2019 and prtage>=18 and prtage<=150 and peb30=1 then 1
else 0 end) pnumge18bnk,
 sum(case when hryear4=2009 then null when hryear4<2019 and prtage>=18 and prtage<=150 and  (pes2a=0 or hes2=2)  then 1 
when hryear4>=2019 and prtage>=18 and prtage<=150 and  (peb30=0 or heb20=2)  then 1 
else 0 end) pnumge18unbnk,
 sum(case when (hryear4=2009 or hryear4>=2019) then null when prtage>180 and prtage<=150 and pes2a not in (0,1) and hes2!=2  then 1 else 0 end) pnumge18unk,


max(case when plivstat=1 then 1 else 0 end) hlivwfam,
max(case when plivstat=4 then 1 else 0 end) hlivwnonfam,

max(case when plivstat_mill=1 then 1 else 0 end) hlivwfam_mill,
max(case when plivstat_mill=4 then 1 else 0 end) hlivwnonfam_mill



from pp 
group by 1')

library(plyr)
write.csv(pp,file=paste('pp_plus_',max(pp$hryear4),'.csv',sep=''),row.names=FALSE)


print(names(pp))
print('*********************************************************')
#changed to keep base nonresp 2015 december
pp<-subset(pp,!prpertyp %in% c(1,3))

if (sum(grepl('pxs|hx|hxs',names(pp)))>0)
{
print('imp')
imp=unique(pp[,grepl('qstnum|perrp|pxs|hx|hxs',names(pp))])
#imp_flags=pp[,grepl('qstnum|perrp|hxp|hxb|hxs|hxt|pxs|hxu|hxu|hxb|hxn|hxl|hxc|hxp',names(pp))]


}


pp=pp[,!grepl('filler|hxu|hxb|hxn|hxl|hxc|hxp',names(pp))]



#pp=pp[,!grepl('px|filler|pea|pel',names(pp))]

#pp=pp[,!grepl('px|filler|pea|pel|pul|hx|puh|peh',names(pp))]
pps=pp[,!grepl('px|filler|pea|pel|pul|puh|peio|pej|prmj|pub|pedi|cow|pur|pui|peer',names(pp))]

ppv=pp[,grepl('qstnum|occurnum|perrp|px|filler|pea|pel|pul|puh|peio|pej|prmj|pub|pedi|cow|pur|pui|peer',names(pp))]




print(length(names(pp)))
print(names(pp))


##cllapse to hh
uniq_hh<-sqldf('select qstnum,min(perrp) perrp from pp  group by 1 order by 1')
uniq_hh<-sqldf('select a.qstnum, a.perrp, min(occurnum) occurnum from uniq_hh a, pp b where a.qstnum=b.qstnum and a.perrp=b.perrp group by 1,2 order by 1,2')

#ppv=sqldf('select pp.* from ppv pp join uniq_hh hh on (pp.qstnum=hh.qstnum and pp.perrp=hh.perrp and pp.occurnum=hh.occurnum)')
ppv=sqldf('select x.* from ppv x , uniq_hh y where x.qstnum=y.qstnum and x.perrp=y.perrp and x.occurnum=y.occurnum')

pp_plus<-sqldf('select x.*,
case when pwsswgt>0 then 1 else 0 end pbaseresp,
case when pwsupwgt>0 then 1 else 0 end psupresp,
case when hh.perrp is not null then 1 else 0 end  hbaseint,
case when hh.perrp is not null and hwhhwgt>0 then 1  else 0 end hbaseresp,
case when hh.perrp is not null and hhsupwgt>0 then 1  else 0 end hsupresp,

case when hryear4= 2009 and hh.perrp is not null and hes31>0 then 1 
	when hryear4>2009 and hh.perrp is not null and hes39>0 then 1  else 0 end hansppq,

case 
     when hryear4=2009 and hh.perrp is not null and hes31>0 then 1
     when hryear4>=2013 and hh.perrp is not null and hes49k>0 then 1  
     when hryear4=2011 and hh.perrp is not null and hes39>0 then 1  
else 0 end hanslstq,

case 
	when hrhtype in (1,2,3,4) then 1
	when hrhtype in (6,7) then 2
	when hrhtype in (5,8,9,10) then 3 
end hhfamtyp,

case 
	when hrhtype in (1,2) then 1
	when hrhtype =4 then 2
	when hrhtype =3 then 3
	when hrhtype=7 then 4
	when hrhtype=6 then 5
else 6 end hhtype,

case 
when hryear4>=2013 and ptdtrace in (2, 6, 10, 11, 12, 16, 17, 18, 22, 23) then 1
when hryear4>=2013 and pehspnon = 1 then 2
when hryear4>=2013 and ptdtrace in (4,8,13,15, 19,21,24) then 3
when hryear4>=2013 and ptdtrace in (3,7,14,20) then 4
when hryear4>=2013 and ptdtrace in (5,9) then 5
when hryear4>=2013 and ptdtrace = 1 then 6
when hryear4>=2013 then 7

	when ptdtrace in (2,6,10,11,12,15,16,19) then  1
	when pehspnon=1 then 2
	when ptdtrace=1 then 6
	when ptdtrace in (4,8,13,14,17,18) then 3
	when ptdtrace in (3,7) then 4
	when ptdtrace in (5,9) then 5
	else 7 end praceeth,

case 

when hryear4>=2013 and ptdtrace in (2, 6, 10, 11, 12, 16, 17, 18, 22, 23) then 1
when hryear4>=2013 and pehspnon = 1 then 2
when hryear4>=2013 and ptdtrace in (4,8,13,15, 19,21,24) then 3
when hryear4>=2013 and ptdtrace = 1 then 4
when hryear4>=2013 then 5

	when ptdtrace in (2,6,10,11,12,15,16,19) then  1
	when pehspnon=1 then 2
	when ptdtrace=1 then 4
	when ptdtrace in (4,8,13,14,17,18) then 3
	else 5 end praceeth2,


case when (ptdtrace = 2 and pehspnon = 2) then 1 
     when pehspnon = 1 then 2 
     when (ptdtrace = 4 and pehspnon = 2) then 3 
     when (ptdtrace = 3 and pehspnon = 2) then 4 
     when (ptdtrace = 5 and pehspnon = 2) then 5 
     when (ptdtrace = 1 and pehspnon = 2) then 6 else 7 end praceeth3,

case 
	when prcitshp in (1,2,3) then 1
	when prcitshp =4 then 2
	when prcitshp=5 then 3
end pnativ,

case 
	when prtage>=15 and prtage<25 then 1
	when prtage>=15 and prtage<35 then 2
	when prtage>=15 and prtage<45 then 3
	when prtage>=15 and prtage<55 then 4
	when prtage>=15 and prtage<65 then 5
	when prtage>=15 and prtage>=65 then 6
end pagegrp,

case 
	when peeduca>=43 then 4
	when peeduca>=40 then 3
	when peeduca>=39 then 2
else 1 end peducgrp,

case when prempnot=1 then 1
     when prempnot=2 then 2
     when prempnot in (3,4) then 3
     when prempnot=-1 then 4
end pempstat,

case  when hryear4=2009 then null
	when hefaminc<0 then 99
	when hefaminc<=5 then 1
	when hefaminc<=8 then 2
	when hefaminc<=11 then 3
	when hefaminc<=13 then 4
else 5 end hhincome,

case  when hryear4=2009 then null
	when hxfaminc>0 then -99 else hefaminc end  hefaminc_adj,

case 
	when hryear4>2009 and hxfaminc>0 then 99
	when hefaminc<0 then 99
	when hefaminc<=5 then 1
	when hefaminc<=8 then 2
	when hefaminc<=11 then 3
	when hefaminc<=13 then 4
else 5 end hhincome2,

case 
	when hefaminc=1 then 2500
	when hefaminc=2 then 6250
	when hefaminc=3 then 8750
	when hefaminc=4 then 11250
	when hefaminc=5 then 13750
	when hefaminc=6 then 17500
	when hefaminc=7 then 22500
	when hefaminc=8 then 27500
	when hefaminc=9 then 32500
	when hefaminc=10 then 37500
	when hefaminc=11 then 45000
	when hefaminc=12 then 55000
	when hefaminc=13 then 67500
	when hefaminc=14 then 87500
	when hefaminc=15 then 125000
	when hefaminc=16 then 175000
else NULL
end hhinc_cont,

case when hetenure=1 then 1 else 2 end hhtenure,

pwsupwgt/10000000.0 psupwgtk,


case when not(hh.qstnum is not null and hhsupwgt>0)
then 0.0 else 
hhsupwgt/10000000.0
end hsupwgtk,

case
when hryear4>=2019 and heb20=2 then 1
when hryear4>=2019 and heb20=1 then 2
when hryear4=2009 and hes1=2 then 1
when hryear4=2009 and hes1=1 then 2 
when hes2=2 then 1
when hes2=1 then 2 
else 99 end hunbnk,


case
     when hryear4>=2019 and (peb30=0 or heb20=2) then 1
     when hryear4>=2019 and peb30=1 then 2
     when hryear4>=2019 then null
     when hryear4=2009 then null
     when pes2a=0 or hes2=2 then 1 
     when pes2a=1 then 2
else 99 end punbnk,

case
     when hryear4>=2019 then null
     when hryear4=2009 then null 
	when pes2b=1 then 1
	when pes2b=2 then 2
	when pes2b=3 then 3
	when pes2b=4 then 4
	when hes2=2 or pes2a = 0 then 5
else 99 end pbnktyp,

case 


when hryear4>=2015 then null
when hryear4<2013 then null
	when hes2c=1 then 1
	when hes2c=2 then 2
	when hes2=2 then -1
else 99 end hdirdep,

case 

when hryear4>=2015 then null
when hryear4<2013 then null
when hes2d1=1 and hes2d2=1 then 1
when  hes2d1 = 1 and hes2d2 = 2  then  2 
when  hes2d1 = 2 and hes2d2 = 1  then  3 
when hes2c=2 then 5
when  hes2 = 2 then  -1 
when hes2c=1 then 4
else  99  end     hddacct  ,

case when (hryear4 < 2013 or hryear4 = 2019 or hryear4 = 2021) then null
when (hryear4 >= 2013 and hryear4 <= 2017) and hes2e = 1 then 1
when (hryear4 >= 2013 and hryear4 <= 2017) and hes2e = 2 then 2
when (hryear4 >= 2013 and hryear4 <= 2017) and hes2 = 2 then -1
when (hryear4 >= 2023) and heb40 = 1 then 1
when (hryear4 >= 2023) and heb40 = 2 then 2
when (hryear4 >= 2023) and heb20 = 2 then -1
end hbnknew,



case 
when hryear4>=2019 and heub10 = 1 then 1
when hryear4>=2019 and heub10 = 2 then 2
when hryear4>=2019 and heb20 = 1 then -1
when hryear4>=2019 then 99
when hes3 = 1 then  1
when  hes3 = 2 then  2
when  hryear4=2009 and hes1 = 1 then  -1  
when  hryear4>2009 and hes2 = 1 then  -1 
else 99 end hbnkprev  ,


case 
when hryear4>=2019 and heub15 = 1 then 1
when hryear4>=2019 and heub15 = 2 then 2
when hryear4>=2019 and heub10 = 2 then 3
when hryear4>=2019 and heb20 = 1 then -1
when hryear4>=2019 then 99
when hes4 = 1 then  1
when  hes4 = 2 then  2
when  hes3 = 2 then  3 
when  hryear4>2009 and hes2 = 1 then  -1
when  hryear4=2009 and hes1 = 1 then  -1 
when hes3=1 then 98
else 99 end hbnkprevly  ,


case
when hryear4 >= 2019 then null
when hryear4=2009 and hes11=1 then 1
when hryear4=2009 and hes11=2 then 2
when hryear4=2009 and hes11=3 then 3
when hryear4=2009 and hes11=4 then 4
when hryear4=2009 and hes1=1 then -1

when hryear4>2009 and  hes7 = 1 then  1 
when hryear4>2009 and   hes7 = 2 then  2 
when hryear4>2009 and   hes7 = 3 then  3 
when hryear4>2009 and   hes7 = 4 then  4 
when hryear4>2009 and   hes2 = 1 then  -1 
else  99  end        hbnkfutr  ,




case 
when hryear4>=2015 then null
when hryear4=2009 and hes14 = 1  then  1 
when hryear4=2009 and hes14 = 2  then  2 
when hes9 = 1  then  1 
when  hes9 = 2 then  2 
else  99  end    huse1CC  ,


case
when hryear4>=2015 then null
when hryear4<2011 then null
when hes10 = 1    then  1 
when  hes9 = 1 and hes10 = 2 then  2 
when  hes9 = 2 then  3 
else  99  end           huse2CC  ,


case 
when hryear4>=2015 then null
when hryear4<2011 then null
when hes11 = 1       then  1 
when  (hes9 = 1 and (hes10 = 2 or hes11 = 2))then  2 
when  hes9 = 2    then  3 
else  99  end                 huse3CC  ,


case 
when hryear4>=2015 then null
when hryear4<2011 then null
when hes11 = 1 then  1 
when  hes10 = 1  then  2 
when  hes9 = 1 then  3 
when  hes9 = 2 then  4 
else 99  end  huseCC  ,

case
when hryear4>=2015 then null
 when hryear4<2013 then null
when  hes10 != 1  then  -1 
when hes13b = 1 then  1 
when  hes13b = 2 then  2 
when  hes13b = 3 then  3 
else  99  end   hplaceCC  ,

case 
when hryear4>=2015 then null
when hryear4=2009 and hes17 = 1  then  1 
when hryear4=2009 and hes17 = 2 then  2 

when  hryear4>2009 and hes14 = 1  then  1 
when  hryear4>2009 and  hes14 = 2 then  2 

else  99  end    huse1MO  ,


case 
when hryear4>=2015 then null
when hryear4<2011 then null
 when hes15 = 1    then  1 
when  hes14 = 1 and hes15 = 2 then  2 
when  hes14 = 2 then  3 
else  99  end           huse2MO  ,


case 
when hryear4>=2015 then null
when hryear4<2011 then null
when hes16 = 1       then  1 
when  (hes14 = 1 and (hes15 = 2 or hes16 = 2))then  2 
when  hes14 = 2    then  3 
else  99  end                 huse3MO  ,


case 
when hryear4>=2015 then null
when hryear4<2011 then null
when hes16 = 1 then  1 
when  hes15 = 1 then  2 
when  hes14 = 1 then  3 
when  hes14 = 2 then  4 
else 99  end  huseMO  ,

case
when hryear4>=2015 then null
when hryear4<2013 then null
when  hes15 != 1  then  -1 
when hes19b = 1 then  1 
when  hes19b = 2 then  2 
when  hes19b = 3 then  3 
when  hes19b = 4 then  4 
else  99  end   hplaceMO  ,



case
when hryear4>=2015 then null
when hryear4<2011 then null
 when hes20 = 1  then  1 
when  hes20 = 2 then  2 
else  99  end    huse1RM  ,


case
when hryear4>=2015 then null

when hryear4<2011 then null
 when hes21 = 1    then  1 
when  hes20 = 1 and hes21 = 2 then  2 
when  hes20 = 2 then  3 
else  99  end           huse2RM  ,


case
when hryear4>=2015 then null
when hryear4<2011 then null
 when hes22 = 1       then  1 
when  (hes20 = 1 and (hes21 = 2 or hes22 = 2))then  2 
when  hes20 = 2    then  3 
else  99  end                 huse3RM  ,


case 
when hryear4 >= 2015 then null
when hryear4 < 2011 then null
when  hes22 = 1 then  1 
when  hes21 = 1 then  2 
when  hes20 = 1 then  3 
when  hes20 = 2 then  4 
else 99  end  huseRM  ,

case 
when hryear4>=2015 then null
when hryear4<2013 then null
when  hes21 != 1  then  -1 
when  hes24b = 1 then  1 
when  hes24b = 2 then  2 
when  hes24b = 3 then  3 
when  hes24b = 4 then  4 
when  hes24b = 5 then  5 
else  99  end   hplaceRM  ,



case 
when hryear4>=2015 then null
when  hryear4=2009 and hes20 = 1  then  1 
when  hryear4=2009 and hes20= 2 then  2 

when  hryear4>2009 and  hes25 = 1  then  1 
when  hryear4>2009 and  hes25 = 2 then  2 
else  99  end    huse1PDL  ,


case
when hryear4>=2015 then null
when hryear4<2011 then null
 when  hes26 = 1    then  1 
when  hes25 = 1 and hes26 = 2 then  2 
when  hes25 = 2 then  3 
else  99  end           huse2PDL  ,


case
when hryear4>=2015 then null
when hryear4<2011 then null
 when  hes27 = 1          then  1 
when  (hes25 = 1 and (hes26 = 2 or hes27 = 2)) then  2 
when  hes25 = 2       then  3 
else  99  end              huse3PDL  ,


case 
when hryear4>=2015 then null
when hryear4<2011 then null
when  hes27 = 1 then  1 
when  hes26 = 1  then  2 
when  hes25 = 1 then  3 
when  hes25 = 2  then  4 
else 99  end  husePDL  ,

case 
when hryear4>=2015 then null
when hryear4<2013 then null
when  hes28b = 1 then  1 
when  hes28b = 2 then  2 
when  hes26 != 1 then  -1
else  99  end  husePDLol  ,



case 
when hryear4>=2015 then null
when hryear4=2009 and hes23 = 1  then  1 
when hryear4=2009 and hes23 = 2 then  2 

when hryear4>2009 and  hes29 = 1  then  1 
when hryear4>2009 and  hes29 = 2 then  2 
else  99  end    huse1PWN  ,


case 
when hryear4>=2015 then null
when hryear4<2011 then null
when  hes30 = 1    then  1 
when  hes29 = 1 and hes30 = 2 then  2 
when  hes29 = 2 then  3 
else  99  end           huse2PWN  ,


case
when hryear4>=2015 then null
when hryear4<2011 then null
when  hes31 = 1          then  1 
when  (hes29 = 1 and (hes30 = 2 or hes31 = 2)) then  2 
when  hes29 = 2       then  3 
else  99  end              huse3PWN  ,


case 
when hryear4>=2015 then null
when hryear4<2011 then null
when  hes31 = 1 then  1 
when  hes30 = 1 then  2 
when  hes29 = 1  then  3 
when  hes29 = 2 then  4 
else 99  end  husePWN  ,



case 
when hryear4>=2015 then null
when hryear4=2009 and hes26 = 1  then  1 
when hryear4=2009 and hes26 = 2 then  2 
when hryear4>2009 and  hes33 = 1  then  1 
when hryear4>2009 and  hes33 = 2 then  2 
else  99  end    huse1RAL  ,


case 
when hryear4>=2015 then null
when hryear4<2011 then null
 when  hes34 = 1    then  1 
when  hes33 = 1 and hes34 = 2 then  2 
when  hes33 = 2 then  3 
else  99  end           huse2RAL  ,



case 

when hryear4>=2015 then null
when hryear4<2011 then null
when  hes34 = 1  then  2 
when  hes33 = 1 then  3 
when  hes33 = 2 then  4 
else 99  end  huseRAL  ,



case 
when hryear4>=2015 then null
when hryear4=2009 and hes27 = 1  then  1 
when hryear4=2009 and hes27 = 2 then  2 

when  hryear4>2009 and hes35 = 1  then  1 
when   hryear4>2009 and hes35 = 2 then  2 

else  99  end    huse1RTO  ,


case 
when hryear4>=2015 then null
when hryear4<2011 then null
when  hes36 = 1    then  1 
when  hes35 = 1 and hes36 = 2 then  2 
when  hes35 = 2 then  3 
else  99  end           huse2RTO  ,

case
when hryear4>=2015 then null
 when hryear4>=2015 then null
 when hryear4<2013 then null
when  hes37 = 1          then  1 
when  (hes35 = 1 and (hes36 = 2 or hes37 = 2)) then  2 
when  hes35 = 2       then  3 
else  99  end              huse3RTO  ,

case 
 when hryear4>=2015 then null 
when hryear4<2013 then null
when  hes37 = 1 then  1 
when  hes36 = 1 then  2 
when  hes35 = 1 then  3 
when  hes35 = 2 then  4 
else 99  end  huseRTO  ,

case 
when hryear4>=2013 then null
when hryear4=2009 and hes30 = 1 		then  1
when hryear4=2009 and hes30 = 2 		then  2
when  hes38 = 1 		then  1
when hes38 = 2 	then 2
else 99 end husesPYRL ,

case 

when hryear4>=2015 then null
when hryear4<2013 then null
when  hes38 = 1  then  1 
when  hes38 = 2 then  2 
else  99  end    huse1ATL  ,

case 

when hryear4>=2015 then null
when hryear4<2013 then null
when  hes38b = 1    then  1 
when  hes38 = 1 and hes38b = 2 then  2 
when  hes38 = 2 then  3 
else  99  end           huse2ATL  ,

case 
when hryear4>=2015 then null
when hryear4<2013 then null
when  hes38c = 1          then  1 
when  (hes38 = 1 and (hes38b = 2 or hes38c = 2)) then  2 
when  hes38 = 2       then  3 
else  99  end              huse3ATL  ,

case 
when hryear4>=2015 then null
when hryear4<2013 then null
when  hes38c = 1 then  1 
when  hes38b = 1 then  2 
when  hes38 = 1 then  3 
when  hes38 = 2 then  4 
else 99  end  huseATL  ,


   case when hryear4<2017 then null when hes127 < -1 then 99 else hes127 end huse12oafsc,


case 
when hryear4>=2015 then null
when hryear4=2009 and hes31 = 1 		then  1
when hryear4=2009 and hes31 = 2 		then  2

when  hryear4>2009 and hes39 = 1  then  1 
when  hryear4>2009 and hes39 = 2 then  2 
else  99  end    huse1PP  ,

case 

when hryear4>=2015 then null
when hryear4<2013 then null
when  hes40 = 1    then  1 
when  hes39 = 1 and hes40 = 2 then  2 
when  hes39 = 2 then  3 
else  99  end           huse2PP  ,

case 
when hryear4>=2015 then null
when hryear4<2013 then null
when  hes41 = 1          then  1 
when  (hes39 = 1 and (hes40 = 2 or hes41 = 2)) then  2 
when  hes39 = 2       then  3 
else  99  end              huse3PP  ,


case 
when hryear4>=2015 then null
when hryear4<2013 then null
when  hes41 = 1 then  1 
when  hes40 = 1 then  2 
when  hes39 = 1 then  3 
when  hes39 = 2 then  4 
else 99  end  husePP  ,

case 

when hryear4>=2015 then null
when hryear4<2013 then null
when  hes43 = 1 then  1 
when  hes43 = 2 then  2 
when  hes43 = 3 then  3 
when  hes43 = 4 then  4 
when  hes43 = 5 then  5 
when  hes43 = 6 then  6 
when  hes43 = 7 then  7 
when  hes40 != 1  then -1 
else   99 end hplacepp,


case 
when hryear4>=2015 then null
when hryear4<2013 then null
when  hes44 = 1 then  1 
when  hes44 = 2 then  2 
when  hes40 != 1 then  -1 
else  99  end  hrloadpp  ,

case 


when hryear4>=2015 then null
when hryear4<2013 then null
when  hes46 = 1 then  1 
when  hes46 = 2 then  2 
else  99  end  hintacc  ,

case 
when hryear4>=2019 then heh20
when hryear4>=2015 and hes185 < -1 then 99
when hryear4>=2015 then hes185
when hryear4<2013 then null
when  hes47 = 1 then  1 
when  hes47 = 2 then  2 
else  99  end  hmphone  ,



case 
when hryear4 >= 2021 then null
when hryear4<2013 then null
when hryear4>=2019 and heh30 = 1 then 1
when hryear4>=2019 and heh30 = 2 and heh20 = 1 then 2
when hryear4>=2019 and heh20 = 2 then 3
when hryear4>=2015 and hryear4<=2017 and hes186 = 1 then 1
when hryear4>=2015 and hryear4<=2017 and hes186 = 2 and hes185 = 1 then 2
when hryear4>=2015 and hryear4<=2017 and hes185 = 2 then 3
when hryear4>=2015 and hryear4<=2017 then 99
when  hes48 = 1 then  1 
when  hes48 = 2 and hes47 = 1 then  2 
when  hes47 = 2 then  3 
else  99  end  hsmphone ,



case  when hryear4>=2015 then null  when hryear4<2013 then null when hes2f <-1 then 99 else hes2f end hbnknewrsn,

case
when hryear4<2013 then null
when hryear4<=2017 and (hes2 = 2 or hes2g7 = 1 or hes2g1 <= -1) then -1
when hryear4<=2017 and hes2h<0 then 98
when hryear4<=2017 then hes2h
when hryear4>=2019 and (heb20=2 or (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2)) then -1
when hryear4>=2019 and heba15=4 then 5
when hryear4>=2019 and heba15=5 then 4
when hryear4>=2019 then heba15
end hbnkaccm,


case when (hryear4<2013 or hryear4>=2019) then null when hes2 = 2 or hes2g7 !=2 then -1 when hes2g1 <-1 then 99 else hes2g1 end hbnkaccm1,
case when (hryear4<2013 or hryear4>=2019) then null when hes2 = 2 or hes2g7 !=2 then -1 when hes2g1 <-1 then 99 else hes2g2 end hbnkaccm2,
case when (hryear4<2013 or hryear4>=2019) then null when hes2 = 2 or hes2g7 !=2 then -1 when hes2g1 <-1 then 99 else hes2g3 end hbnkaccm3,
case when (hryear4<2013 or hryear4>=2019) then null when hes2 = 2 or hes2g7 !=2 then -1 when hes2g1 <-1 then 99 else hes2g4 end hbnkaccm4,
case when (hryear4<2013 or hryear4>=2019) then null when hes2 = 2 or hes2g7 !=2 then -1 when hes2g1 <-1 then 99 else hes2g5 end hbnkaccm5,
case when (hryear4<2013 or hryear4>=2019) then null when hes2 = 2 or hes2g7 !=2 then -1 when hes2g1 <-1 then 99 else hes2g6 end hbnkaccm6,
case when (hryear4<2013 or hryear4>=2019) then null when hes2g1 <-1 then 99 when hes2 = 2 then -1 else hes2g7 end hbnkaccm7,



case  when hryear4>=2015 then null  when hryear4<2013 then null when hes2i1 <-1 then 99 else hes2i1 end hbnkmob1,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes2i1 <-1 then 99 else hes2i2 end hbnkmob2,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes2i1 <-1 then 99 else hes2i3 end hbnkmob3,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes2i1 <-1 then 99 else hes2i4 end hbnkmob4,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes2i1 <-1 then 99 else hes2i5 end hbnkmob5,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes2i1 <-1 then 99 else hes2i6 end hbnkmob6,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes2i1 <-1 then 99 else hes2i7 end hbnkmob7,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes2i1 <-1 then 99 else hes2i8 end hbnkmob8,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes2i1 <-1 then 99 else hes2i9 end hbnkmob9,

case  when hryear4>=2015 then null  when hryear4<2013 then null  when not(hes2=1 or hes4=1) then -1  when hes2i1=1 then 1 when hes2i1=2 then 2 when hes2g5=2 then 2 else 99  end hbnkmob1bnk,
case  when hryear4>=2015 then null  when hryear4<2013 then null  when not(hes2=1 or hes4=1) then -1  when hes2i2=1 then 1 when hes2i2=2 then 2 when hes2g5=2 then 2 else 99   end hbnkmob2bnk,
case  when hryear4>=2015 then null  when hryear4<2013 then null  when not(hes2=1 or hes4=1) then -1  when hes2i3=1 then 1 when hes2i3=2 then 2 when hes2g5=2 then 2 else 99   end hbnkmob3bnk,
case  when hryear4>=2015 then null  when hryear4<2013 then null  when not(hes2=1 or hes4=1) then -1  when hes2i4=1 then 1 when hes2i4=2 then 2 when hes2g5=2 then 2 else 99   end hbnkmob4bnk,
case  when hryear4>=2015 then null  when hryear4<2013 then null  when not(hes2=1 or hes4=1) then -1  when hes2i5=1 then 1 when hes2i5=2 then 2 when hes2g5=2 then 2 else 99   end hbnkmob5bnk,
case  when hryear4>=2015 then null  when hryear4<2013 then null  when not(hes2=1 or hes4=1) then -1  when hes2i6=1 then 1 when hes2i6=2 then 2 when hes2g5=2 then 2 else 99   end hbnkmob6bnk,
case  when hryear4>=2015 then null  when hryear4<2013 then null  when not(hes2=1 or hes4=1) then -1  when hes2i7=1 then 1 when hes2i7=2 then 2 when hes2g5=2 then 2 else 99   end hbnkmob7bnk,
case  when hryear4>=2015 then null  when hryear4<2013 then null  when not(hes2=1 or hes4=1) then -1  when hes2i8=1 then 1 when hes2i8=2 then 2 when hes2g5=2 then 2 else 99   end hbnkmob8bnk,
case  when hryear4>=2015 then null  when hryear4<2013 then null  when not(hes2=1 or hes4=1) then -1  when hes2i9=1 then 1 when hes2i9=2 then 2 when hes2g5=2 then 2 else 99   end hbnkmob9bnk,



case when hryear4<2017 then null when hryear4 >= 2019 then null when hryear4=2017 and not(hes2 = 1 or hes4 = 1) then -1 when hes80a=1 then 1 when hes80a=2 then 2 else 99 end hbnkmobv2a,
case when hryear4<2017 then null when hryear4 >= 2019 then null when not(hes2 = 1 or hes4 = 1) then -1 when hes80b=1 then 1 when hes80b=2 then 2 else 99 end hbnkmobv2b,
case when hryear4<2017 then null when hryear4 >= 2019 then null when  not(hes2 = 1 or hes4 = 1) then -1 when hes80c=1 then 1 when (hes80c=2 or hes2g5 = 2)  then 2 else 99 end hbnkmobv2c,
case when hryear4<2017 then null when hryear4 >= 2019 then null when not(hes2 = 1 or hes4 = 1) then -1 when hes80d=1 then 1 when hes80d=2 or hes2g5=2 then 2 else 99 end hbnkmobv2d,
case when hryear4<2017 then null when hryear4 >= 2019 then null when  not(hes2 = 1 or hes4 = 1) then -1 when hes80e=1 then 1 when hes80e=2 or hes2g5=2 then 2 else 99 end hbnkmobv2e,
case when hryear4<2017 then null when hryear4 >= 2019 then null when  not(hes2 = 1 or hes4 = 1) then -1 when hes80f=1 then 1 when hes80f=2 or hes2g5=2 then 2 else 99 end hbnkmobv2f,
case when hryear4<2017 then null when hryear4 >= 2019 then null when  not(hes2 = 1 or hes4 = 1) then -1 when hes80g=1 then 1 when hes80g=2  or hes2g5=2 then 2 else 99 end hbnkmobv2g,


case   when hryear4<=2015 then null when hryear4 >= 2019 then null when hryear4=2017 and hes2g5!=1 then -1   when hryear4=2017 and not(hes2 = 1 or hes4 = 1) then -1 when hes80a=1 then 1 when hes80a=2 then 2 else 99 end hbnkmobv2a_c,
case   when hryear4<=2015 then null when hryear4 >= 2019 then null when hryear4=2013 and hes2i1 <-1 then 99 when hryear4=2013 then hes2i4 when hryear4=2017 and hes2g5!=1 then -1   when hryear4=2017 and not(hes2 = 1 or hes4 = 1) then -1 when hes80b=1 then 1 when hes80b=2 then 2 else 99 end hbnkmobv2b_c,
case   when hryear4<=2015 then null when hryear4 >= 2019 then null when hryear4=2013 and hes2i1 <-1 then 99 when hryear4=2013 then hes2i2  when hryear4=2017 and hes2g5!=1 then -1   when hryear4=2017 and not(hes2 = 1 or hes4 = 1) then -1 when hes80c=1 then 1 when hes80c=2 then 2 else 99 end hbnkmobv2c_c,
case   when hryear4<=2015 then null when hryear4 >= 2019 then null  when hryear4=2013 and hes2i1 <-1 then 99 when hryear4=2013 then hes2i3   when hryear4=2017 and hes2g5!=1 then -1   when hryear4=2017 and not(hes2 = 1 or hes4 = 1) then -1 when hes80d=1 then 1 when hes80d=2 then 2 else 99 end hbnkmobv2d_c,
case   when hryear4<=2015 then null when hryear4 >= 2019 then null when hryear4=2013 and hes2i1 <-1 then 99 when hryear4=2013 then hes2i5    when hryear4=2017 and hes2g5!=1 then -1   when hryear4=2017 and not(hes2 = 1 or hes4 = 1) then -1 when hes80e=1 then 1 when hes80e=2 then 2 else 99 end hbnkmobv2e_c,
case   when hryear4<=2015 then null when hryear4 >= 2019 then null  when hryear4=2013 and hes2i1 <-1 then 99 when hryear4=2013 then hes2i6    when hryear4=2017 and hes2g5!=1 then -1   when hryear4=2017 and not(hes2 = 1 or hes4 = 1) then -1 when hes80f=1 then 1 when hes80f=2 then 2 else 99 end hbnkmobv2f_c,
case   when hryear4<=2015 then null when hryear4 >= 2019 then null when hryear4=2013 and hes2i1 <-1 then 99 when hryear4=2013 then hes2i7    when hryear4=2017 and hes2g5!=1 then -1   when hryear4=2017 and not(hes2 = 1 or hes4 = 1) then -1 when hes80g=1 then 1 when hes80g=2 then 2 else 99 end hbnkmobv2g_c,




case  when hryear4>=2015 then null  when hryear4<2013 then null when hes421 <-1 then 99 else hes421 end huseppr1,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes421 <-1 then 99 else hes422 end huseppr2,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes421 <-1 then 99 else hes423 end huseppr3,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes421 <-1 then 99 else hes424 end huseppr4,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes421 <-1 then 99 else hes425 end huseppr5,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes421 <-1 then 99 else hes426 end huseppr6,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes421 <-1 then 99 else hes427 end huseppr7,


case 
when hryear4>=2015 then null
when hryear4>=2015 and hes5a1 = 1 or hes5a2 = 1 then  1 when hryear4>=2015 and hes5a1 = 2 and hes5a2 = 2 then 2  
when hryear4>=2015 and hes5a1= -1 then -1 when hryear4>=2015 then 99 when hryear4<2013 then null 
when hes5a <-1 then 99 else hes5a end hunbnkr1,

case 
when hryear4>=2015 then null
when hryear4>=2015 and hes5b1 = 1 or hes5b2 = 1 then 1
when hryear4>=2015 and (hes5b1 = 2 and hes5b2 = 2) then 2
when hryear4>=2015 and hes5b1= -1 then -1
when hryear4>=2015 then 99
when hryear4<2013 then null 
when hes5b <-1 then 99 else hes5b end hunbnkr2,

case 
when hryear4>=2015 then null
when hryear4>=2015 and hes5c < -1 then 99 when hryear4>=2015 then hes5c
when hryear4<2013 then null when hes5c <-1 then 99 else hes5c end hunbnkr3,


case 
when hryear4>=2015 then null
when hryear4>=2015 and hes5d < -1 then 99 when hryear4>=2015 then hes5d
when hryear4<2013 then null when hes5d <-1 then 99 else hes5d end hunbnkr4,


case 
when hryear4>=2015 then null
when hryear4>=2015 and hes5e < -1 then 99 when hryear4>=2015 then hes5e
when hryear4<2013 then null when hes5e <-1 then 99 else hes5e end hunbnkr5,

case
when hryear4>=2015 then null
when hryear4>=2015 and hes5f < -1 then 99 when hryear4>=2015 then hes5f
 when hryear4<2013 then null when hes5f <-1 then 99 else hes5f end hunbnkr6,

case 
when hryear4>=2015 then null
when hryear4>=2015 and hes5g < -1 then 99 when hryear4>=2015 then hes5g
when hryear4<2013 then null when hes5g <-1 then 99 else hes5g end hunbnkr7,

case 
when hryear4>=2015 then null
when hryear4>=2015 and hes5h < -1 then 99 when hryear4>=2015 then hes5h
when hryear4<2013 then null when hes5h <-1 then 99 else hes5h end hunbnkr8,


	
	
case 
when hryear4>=2015 then null
when hryear4<2013 then null when  (hes6 = -1 and hes2 = 2) or hes6 < -1 then 99 
when hryear4>=2015 and hes6 in (1,2) then 1
when hryear4>=2015 and hes6 in (3,4) then 2
when hryear4>=2015 and hes6 =5 then 3
when hryear4>=2015 and hes6 =6 then 4
when hryear4>=2015 and hes6 =7 then 5
when hryear4>=2015 and hes6 =8 then 6
when hryear4>=2015 and hes6 =9 then 7
when hryear4>=2015 and hes6 =10 then 8
else hes6 end hunbnkrmv2,


case  when hryear4>=2015 then null when hryear4<2013 then null when   (hes42b = -1 and hes40 = 1) or hes42b < -1 then 99 else hes42b end husepprm,


case  when hryear4>=2015 then null  when hryear4<2013 then null when hes451 <-1 then 99 else hes451 end hrloadppm1,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes451 <-1 then 99 else hes452 end hrloadppm2,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes451 <-1 then 99 else hes453 end hrloadppm3,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes451 <-1 then 99 else hes454 end hrloadppm4,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes451 <-1 then 99 else hes455 end hrloadppm5,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes451 <-1 then 99 else hes456 end hrloadppm6,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes451 <-1 then 99 else hes457 end hrloadppm7,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes451 <-1 then 99 else hes458 end hrloadppm8,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes45b1 <-1 then 99 else hes45b1 end hmphoneppu1,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes45b1 <-1 then 99 else hes45b2 end hmphoneppu2,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes45b1 <-1 then 99 else hes45b3 end hmphoneppu3,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes45b1 <-1 then 99 else hes45b4 end hmphoneppu4,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes45b1 <-1 then 99 else hes45b5 end hmphoneppu5,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes45b1 <-1 then 99 else hes45b6 end hmphoneppu6,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes45b1 <-1 then 99 else hes45b7 end hmphoneppu7,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes45b1 <-1 then 99 else hes45b8 end hmphoneppu8,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes45b1 <-1 then 99 else hes45b9 end hmphoneppu9,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes49a <-1 then 99 else hes49a end hevent1,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes49b <-1 then 99 else hes49b end hevent2,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes49c <-1 then 99 else hes49c end hevent3,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes49d <-1 then 99 else hes49d end hevent4,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes49e <-1 then 99 else hes49e end hevent5,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes49f <-1 then 99 else hes49f end hevent6,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes49g <-1 then 99 else hes49g end hevent7,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes49h <-1 then 99 else hes49h end hevent8,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes49i <-1 then 99 else hes49i end hevent9,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes49j <-1 then 99 else hes49j end hevent10,
case  when hryear4>=2015 then null  when hryear4<2013 then null when hes49k <-1 then 99 else hes49k end hevent11,


case when hryear4!=2013 then null when hes2e!=1 then -1 when (hes49a<-1 or hes50a<-1) then 99 when hes49a=2 then 2 else hes50a end hevent1bo,
case when hryear4!=2013 then null when hes2e!=1 then -1 when (hes49b<-1 or hes50b<-1) then 99 when hes49b=2 then 2 else hes50b end hevent2bo,
case when hryear4!=2013 then null when hes2e!=1 then -1 when (hes49c<-1 or hes50c<-1) then 99 when hes49c=2 then 2 else hes50c end hevent3bo,
case when hryear4!=2013 then null when hes2e!=1 then -1 when (hes49d<-1 or hes50d<-1) then 99 when hes49d=2 then 2 else hes50d end hevent4bo,
case when hryear4!=2013 then null when hes2e!=1 then -1 when (hes49e<-1 or hes50e<-1) then 99 when hes49e=2 then 2 else hes50e end hevent5bo,
case when hryear4!=2013 then null when hes2e!=1 then -1 when (hes49f<-1 or hes50f<-1) then 99 when hes49f=2 then 2 else hes50f end hevent6bo,
case when hryear4!=2013 then null when hes2e!=1 then -1 when (hes49g<-1 or hes50g<-1) then 99 when hes49g=2 then 2 else hes50g end hevent7bo,
case when hryear4!=2013 then null when hes2e!=1 then -1 when (hes49h<-1 or hes50h<-1) then 99 when hes49h=2 then 2 else hes50h end hevent8bo,
case when hryear4!=2013 then null when hes2e!=1 then -1 when (hes49i<-1 or hes50i<-1) then 99 when hes49i=2 then 2 else hes50i end hevent9bo,
case when hryear4!=2013 then null when hes2e!=1 then -1 when (hes49j<-1 or hes50j<-1) then 99 when hes49j=2 then 2 else hes50j end hevent10bo,
case when hryear4!=2013 then null when hes2e!=1 then -1 when (hes49k<-1 or hes50k<-1) then 99 when hes49k=2 then 2 else hes50k end hevent11bo,

case when hryear4!=2013 then null when hes4!=1 then -1 when (hes49a<-1 or hes51a<-1) then 99 when hes49a=2 then 2 else hes51a end hevent1bc,
case when hryear4!=2013 then null when hes4!=1 then -1 when (hes49b<-1 or hes51b<-1) then 99 when hes49b=2 then 2 else hes51b end hevent2bc,
case when hryear4!=2013 then null when hes4!=1 then -1 when (hes49c<-1 or hes51c<-1) then 99 when hes49c=2 then 2 else hes51c end hevent3bc,
case when hryear4!=2013 then null when hes4!=1 then -1 when (hes49d<-1 or hes51d<-1) then 99 when hes49d=2 then 2 else hes51d end hevent4bc,
case when hryear4!=2013 then null when hes4!=1 then -1 when (hes49e<-1 or hes51e<-1) then 99 when hes49e=2 then 2 else hes51e end hevent5bc,
case when hryear4!=2013 then null when hes4!=1 then -1 when (hes49f<-1 or hes51f<-1) then 99 when hes49f=2 then 2 else hes51f end hevent6bc,
case when hryear4!=2013 then null when hes4!=1 then -1 when (hes49g<-1 or hes51g<-1) then 99 when hes49g=2 then 2 else hes51g end hevent7bc,
case when hryear4!=2013 then null when hes4!=1 then -1 when (hes49h<-1 or hes51h<-1) then 99 when hes49h=2 then 2 else hes51h end hevent8bc,
case when hryear4!=2013 then null when hes4!=1 then -1 when (hes49i<-1 or hes51i<-1) then 99 when hes49i=2 then 2 else hes51i end hevent9bc,
case when hryear4!=2013 then null when hes4!=1 then -1 when (hes49j<-1 or hes51j<-1) then 99 when hes49j=2 then 2 else hes51j end hevent10bc,
case when hryear4!=2013 then null when hes4!=1 then -1 when (hes49k<-1 or hes51k<-1) then 99 when hes49k=2 then 2 else hes51k end hevent11bc,




case when hryear4<2015 then null when hes5a1 < -1 then 99 else hes5a1 end hunbnkr1v3,
case when hryear4<2015 then null when hes5a2 < -1 then 99 else hes5a2 end hunbnkr2v3,
case when hryear4<2015 then null when hes5b1 < -1 then 99 else hes5b1 end hunbnkr3v3,
case when hryear4<2015 then null when hes5b2 < -1 then 99 else hes5b2 end hunbnkr4v3,
case when hryear4<2015 then null when hes5c < -1 then 99 else hes5c end hunbnkr5v3,
case when hryear4<2015 then null when hes5d < -1 then 99 else hes5d end hunbnkr6v3,
case when hryear4<2015 then null when hes5e < -1 then 99 else hes5e end hunbnkr7v3,
case when hryear4<2015 then null when hes5f < -1 then 99 else hes5f end hunbnkr8v3,
case when hryear4<2015 then null when hes5g < -1 then 99 else hes5g end hunbnkr9v3,
case when hryear4<2015 then null when hes5h < -1 then 99 else hes5h end hunbnkr10v3,


case when hryear4<2015 then null when (hes6 = -1 and hes2 = 2) or hes6 < -1 then 98 else hes6 end hunbnkrmv3 ,




case when hryear4!=2015 then null when hes101 = -2 then 98 else hes101 end hbnkintsrv,


case 
when hryear4<2013 then null
when hryear4>=2019 then hep10
when hryear4=2013 and hes40 = 1    then  1 
when  hryear4=2013 and ((hes39 = 1 and hes40 = 2) or hes39 = 2) then  2 
when  hryear4=2013 then 99
when hes110 < -1 then 99 else hes110 end huse12pp,


case when hes1111 < -1 then 99 else hes1111 end hppwhere1,
case when hes1111 < -1 then 99 else hes1112 end hppwhere2,
case when hes1111 < -1 then 99 else hes1113 end hppwhere3,
case when hes1111 < -1 then 99 else hes1114 end hppwhere4,
case when hes1111 < -1 then 99 else hes1115 end hppwhere5,
case when hes1111 < -1 then 99 else hes1116 end hppwhere6,

case when (hryear4<2015 or hryear4>2017) then null when hes1111 < -1 then 1 when hes1111 > 0 then 2 else -1  end hppwhere99,

case when hes1121< -1 then 99 else hes1121 end hppgovrsn1 ,
case when hes1121< -1 then 99 else hes1122 end hppgovrsn2 ,
case when hes1121< -1 then 99 else hes1123 end hppgovrsn3 ,
case when hes1121< -1 then 99 else hes1124 end hppgovrsn4 ,


case 
when hryear4<2011 then null
when hryear4>=2019 then henbcc10
when hryear4 <2015 and hes10 = 1    then  1 
when  hryear4 <2015 and ((hes9 = 1 and hes10 = 2) or hes9 = 2) then  2 
when   hryear4 <2015 then 99
when hes120 < -1 then 99 else hes120 end huse12cc,

case 
when hryear4<2011 then null
when hryear4>=2019 then henbmo10
when hryear4 <2015 and hes15 = 1    then  1 
when hryear4 <2015 and  ((hes14 = 1 and hes15 = 2) or hes14 = 2) then  2 
when hryear4 <2015 then 99 
when hes121 < -1 then 99 else hes121 end huse12mo,

case 
when hryear4>=2019 then hecnbpdl


when hryear4<2011 then null
when  hryear4 <2015 and hes26 = 1    then  1 
when  hryear4 <2015 and ((hes25 = 1 and hes26 = 2) or hes25 = 2) then  2 
when hryear4 <2015 then 99
when hes122 < -1 then 99 else hes122 end huse12pdl,

case 
when hryear4>=2019 then hecnbpwn
when hryear4<2011 then null
when  hryear4 <2015 and hes30 = 1    then  1 
when  hryear4 <2015 and ((hes29 = 1 and hes30 = 2) or hes29 = 2) then  2 
when  hryear4 <2015 then 99
when hes123 < -1 then 99 else hes123 end huse12pwn,

case 
when hryear4>=2023 then null
when hryear4<2011 then null
when hryear4>=2019 then hecnbtax
when  hryear4 <2015 and hes34 = 1    then  1 
when  hryear4 <2015 and ((hes33 = 1 and hes34 = 2) or hes33 = 2) then  2 
when  hryear4 <2015 then 99
when hes124 < -1 then 99 else hes124 end huse12ral,

case 
when hryear4>=2019 then hecnbrto
when hryear4<2011 then null
when  hryear4 <2015 and hes36 = 1    then  1 
when  hryear4 <2015 and ((hes35 = 1 and hes36 = 2) or hes35 = 2) then  2 
when  hryear4 <2015 then 99
when hes125 < -1 then 99 else hes125 end huse12rto,

case 
when hryear4<2013 then null
when hryear4>=2019 then hecnbatl
when  hryear4 =2013 and hes38b = 1    then  1 
when  hryear4 =2013 and ((hes38 = 1 and hes38b = 2) or hes38 = 2) then  2 
when  hryear4 =2013 then 99
when hes126 < -1 then 99 else hes126 end huse12atl,



case when hes130 < -1 then 99 else hes130 end huse12rmany ,
case when (hryear4<2015 or hryear4>2017) then null when hes131 = 1 then 1 when hes131 = 2 or hes130 = 2 then 2  when hryear4=2017 and hes1351 = 1 then 1 
when hryear4=2017 and  (hes1351 = 2 or hes130 = 2) then 2 else 99 end huse12rmbnk ,




case when hryear4!=2015 then null when hes132 = 1 then 1 when hes132 = 2 or hes131 = 2 or hes130 = 2 then 2 else 99 end  htyprmbnk  ,


case 
      when hryear4>=2021 then null
when hryear4<2011 then null
when hryear4>=2019 then henbrm10
when hryear4 <2015 and  hes21 = 1    then  1 
when  hryear4 <2015 and  ((hes20 = 1 and hes21 = 2) or hes20 = 2) then  2 
when  hryear4 <2015 then 99
when hryear4=2015 and hes133 = 1 then 1 when hryear4=2015 and ( hes133 = 2 or hes130 = 2) then 2 
when hryear4>=2017 and hes1352 = 1 then 1 when hryear4>=2017 and (hes1352 = 2 or hes130 = 2) then 2 

else 99 end  huse12rm ,






case 
 when hryear4<2015 or hryear4>2017 then null
 when hryear4=2015 and   hes133=1 and hes131=2 then 1
 when hryear4=2015 and   hes133=1 and hes131=1 then 2
 when hryear4=2015 and   hes133=2 and hes131=1 then 3
 when hryear4=2015 and   hes130 = 1 and ((hes131 < 0 or hes133 < 0) or (hes131 = 2 and hes133 = 2)) then 4
 when hryear4=2015 and   hes130=2 then 5
 when hryear4=2015 and   hes130<0 then 6 

 when hryear4=2017 and  hes1351 = 1 and hes1352 = 1 then 2
 when hryear4=2017 and  hes1351 = 1 and hes1352 = 2 then 3
 when hryear4=2017 and  hes1351 = 2 and hes1352 = 1 then 1
 when hryear4=2017 and  hes130 = 1 then 4
 when hryear4=2017 and  hes130 = 2 then 5
 when hryear4=2017 and  hes130 < 1 then 6


end huse12rmtype,



case 
 when hryear4 !=2015 then null
 when hes134=1 and (hes132=2 or hes131=2 ) then 1
 when hes134=1 and hes132=1 then 2
 when (hes133=2 or hes134=2) and hes132=1 then 3
 when hes130 = 1  and ((hes133 = 2 or hes134 = 2) and (hes131 = 2 or hes132 = 2))   then 4
 when hes130=2 then 5
 else 6 end htyprmtype,


case when hryear4!=2015 then null  when hes134 = 1 then 1 when hes134 = 2 or hes130 = 2 or hes133 = 2  then 2 else 99 end  htyprmnbnk ,








case when hryear4>=2019 then heccc10 when hryear4>=2017 and hes1600a < -1 then -1 when hryear4>=2017 then hes1600a   when hes160 < -1 then -1 else hes160 end hcred12cc ,

case when hryear4 >= 2023 then null when hryear4<2015 then null when hryear4=2017 then null when hryear4>=2019 then hecpl10 when hes161 < -1 then -1 else hes161 end hcred12bnk ,

case when (hryear4 < 2017 or hryear4 = 2019 or hryear4 = 2021) then null when (hryear4 >= 2023) then hecpl10 when (hryear4 = 2017) then hes1600f end hcred12bnkv2,


case
when hryear4 >= 2023 then null 
when hryear4<2015 then null
when hryear4=2017 then null
when hryear4=2015 and (hes160 = 1 or hes161 = 1) then 1
when hryear4=2015 and (hes160 = 2 and hes161 = 2) then 2
when hryear4=2015 then -1
when hryear4>=2019 and (heccc10 = 1 or hecpl10 = 1) then 1
when hryear4>=2019 and (heccc10 = 2 and hecpl10 = 2) then 2
end hcred12ccorbnk,



case when (hryear4 < 2017 or hryear4 = 2019 or hryear4 = 2021) then null when (hryear4 = 2017) then hes1600b when (hryear4 >= 2023) then hecsc10 end hcred12sc,
case when (hryear4 < 2017 or hryear4 = 2019 or hryear4 = 2021) then null when (hryear4 = 2017) then hes1600c when (hryear4 >= 2023) then hecal10 end hcred12car,
case when (hryear4 < 2017 or hryear4 = 2019 or hryear4 = 2021) then null when (hryear4 = 2017) then hes1600d when (hryear4 >= 2023) then hechmln10 end hcred12hmln,
case when (hryear4 < 2017 or hryear4 = 2019 or hryear4 = 2021) then null when (hryear4 = 2017) then hes1600e when (hryear4 >= 2023) then hecsl10 end hcred12sl,
case when (hryear4 < 2017 or hryear4 = 2019 or hryear4 = 2021) then null when (hryear4 = 2017) then hes1600g when (hryear4 >= 2023) then hecnbpl10 end hcred12oth,



case
when (hryear4 <= 2015 or hryear4 = 2019 or hryear4 = 2021) then null 
when (hryear4 = 2017) and (hes1600a = 1 or hes1600b = 1 or hes1600c = 1 or hes1600d = 1 or hes1600e = 1 or hes1600f = 1 or hes1600g = 1) then 1
when (hryear4 = 2017) and (hes1600a = 2 and hes1600b = 2 and hes1600c = 2 and hes1600d = 2 and hes1600e = 2 and hes1600f = 2 and hes1600g = 2) then 2
when (hryear4 >= 2023) and (heccc10 = 1 or hecsc10 = 1 or hecal10 = 1 or hechmln10 = 1 or hecsl10 = 1 or hecpl10 = 1 or hecnbpl10 = 1) then 1
when (hryear4 >= 2023) and (heccc10 = 2 and hecsc10 = 2 and hecal10 = 2 and hechmln10 = 2 and hecsl10 = 2 and hecpl10 = 2 and hecnbpl10 = 2) then 2
end hcred12any,
case
when (hryear4 <= 2015 or hryear4 = 2019 or hryear4 = 2021) then null 
when (hryear4 = 2017) and (hes1600a = 2 and hes1600b = 2 and hes1600c = 2 and hes1600d = 2 and hes1600e = 2 and hes1600f = 2 and hes1600g = 2) then 1
when (hryear4 = 2017) and (hes1600a = 1 or hes1600b = 1 or hes1600c = 1 or hes1600d = 1 or hes1600e = 1 or hes1600f = 1 or hes1600g = 1) then 2
when (hryear4 >= 2023) and (heccc10 = 2 and hecsc10 = 2 and hecal10 = 2 and hechmln10 = 2 and hecsl10 = 2 and hecpl10 = 2 and hecnbpl10 = 2) then 1
when (hryear4 >= 2023) and (heccc10 = 1 or hecsc10 = 1 or hecal10 = 1 or hechmln10 = 1 or hecsl10 = 1 or hecpl10 = 1 or hecnbpl10 = 1) then 2
end hcred12none,




case when hryear4<2015 then null when hryear4>=2019 then heca10 when hes162< -1 then -1 else hes162 end hcred12newapp , 

case
when hryear4>=2019 and heca10 = 2 then -1
when hryear4>=2019 then heca15
when hes162!=1 then -1
when hes162 = 2 then 2
when hes163 < -1 or hes162 < -1 then -1
else hes163
end hcred12deniedc ,	
case when hryear4<2015 then null when (hryear4>=2019 and heca10=2) then 2 when hryear4>=2019 then heca15 when hes162 = 2  then 2 when hes163 < -1 or hes162 < -1 then -1 else hes163 end hcred12denied ,	
		
case when hryear4<2015 then null when hryear4>=2019 then heca20 when hes164 < -1 then -1 else hes164 end hcred12discour ,

case when hryear4<2015 then null when hryear4>=2019 then hes10 when hes170 < -1 then -1 else hes170 end hsav12,

case when hes1711 <-1 then 99 else hes1711 end hsav12typ1,
case when hes1711 <-1 then 99 else hes1712 end hsav12typ2,
case when hes1711 <-1 then 99 else hes1713 end hsav12typ3,
case when hes1711 <-1 then 99 else hes1714 end hsav12typ4,
case when hes1711 <-1 then 99 else hes1715 end hsav12typ5,
case when hes1711 <-1 then 99 else hes1716 end hsav12typ6,
case when hes1711 <-1 then 99 else hes1717 end hsav12typ7,

case when hes170 =2 or hes170 < -1 then -1 when hes170 =1 and hes1711 < -1 then 1  when hes170 =1 and (hes1711 in (1,2) ) then 2 end hsav12typ99,




case when (hryear4 < 2015 or hryear4 = 2021) then null 
when (hryear4 = 2015 or hryear4 = 2017) then hes180 when (hryear4 = 2019 or hryear4 >= 2023) then heh10 end hincvol,
case
when (hryear4 < 2015 or hryear4 = 2021) then null
when (hryear4 = 2015 or hryear4 = 2017) and hes180 = 1 then 1
when (hryear4 = 2015 or hryear4 = 2017) and hes180 in (2,3) then 2
when (hryear4 = 2019 or hryear4 >= 2023) and heh10 = 1 then 1
when (hryear4 = 2019 or hryear4 >= 2023) and heh10 in (2,3) then 2
end hincvolv2,



case when (hryear4 < 2015 or hryear4 = 2019 or hryear4 = 2021) then null when (hryear4 >= 2023) then heh15 when (hryear4 = 2015 or hryear4 = 2017) then hes181 end hbilldq,


case when hes182 < -1  then 99 else hes182 end hfinfobnk ,
case when hes183 < -1  then 99 else hes183 end hfinedu ,
case when hes184 < -1  then 99 else hes184 end hfinedbnk ,
case when hryear4<2015 then null when hryear4>=2019 then heh40 when hes187 <-1 then 99 else hes187 end hintaccv2,




case 
when prtage=85 or (hryear4-prtage>=1928 and hryear4-prtage<=1945) then 1 
when hryear4-prtage>=1946 and hryear4-prtage<=1964 then 2
when hryear4-prtage>=1965 and hryear4-prtage<=1981 then 3
when hryear4-prtage>=1982 and hryear4-prtage<=2000 then 4
else 5 end pgen


from pps x , uniq_hh hh where x.qstnum=hh.qstnum and x.perrp=hh.perrp and x.occurnum=hh.occurnum')






print(names(pp_plus))
print('aaaa')

#pp_plus=pp_plus[,!grepl('px|filler|pea|pel|pul|hx|puh|peh',names(pp_plus))]

pp_plus=pp_plus[,!grepl('filler',names(pp_plus))]

pp_plus=sqldf('select a.* ,
case 
when hryear4=2009 and hunbnk = 1 then 1
when hryear4=2009 and hunbnk=2 and (hes15 in (1,2) or hes18 in (1,2) or hts21>0 or hes24 in (1,2) or hes28 in (1,2) or hes26 = 1) then 2
when hryear4=2009 and hunbnk=2 and ((hes14 = 2 or hes15 = 3)  and  (hes17 = 2 or hes18 = 3)  and (hes20 = 2 or hts21 = 0) and (hes23 = 2 or hes24 = 3) and (hes26 = 2 ) and (hes27 = 2 or hes28 = 3)) then 3

when hryear4=2009 then 4 
else null end hbankstat,

case 

when hryear4<2015 and  gtcbsa = 11300 then 0
when hryear4<2015 and  gtcbsa = 11340 then 0
when hryear4<2015 and  gtcbsa = 26100 then 0
when hryear4<2015 and  gtcbsa = 39100 then 0
when hryear4<2015 and  gtcbsa = 72850 then 0
when hryear4<2015 and  gtcbsa = 74500 then 0
when hryear4<2015 and  gtcbsa = 77350 then 0
when hryear4<2015 and  gtcbsa = 78700 then 0

when hryear4<2015 and   gtcbsa = 26180 then 46520
when hryear4<2015 and   gtcbsa = 31100 then 31080
when hryear4<2015 and   gtcbsa = 42060 then 42200
when hryear4<2015 and   gtcbsa = 22460 then 22520
when hryear4<2015 and   gtcbsa = 42260 then 35840
when hryear4<2015 and   gtcbsa = 46940 then 42680
when hryear4<2015 and   gtcbsa = 14060 then 14010
when hryear4<2015 and   gtcbsa = 23020 then 18880
when hryear4<2015 and   gtcbsa = 70750 then 12620
when hryear4<2015 and   gtcbsa = 70900 then 12700
when hryear4<2015 and   gtcbsa = 71650 then 14460
when hryear4<2015 and   gtcbsa = 71950 then 14860
when hryear4<2015 and   gtcbsa = 72400 then 15540
when hryear4<2015 and   gtcbsa = 73450 then 25540
when hryear4<2015 and   gtcbsa = 75700 then 35300
when hryear4<2015 and   gtcbsa = 76450 then 35980
when hryear4<2015 and   gtcbsa = 76750 then 38860
when hryear4<2015 and   gtcbsa = 77200 then 39300
when hryear4<2015 and   gtcbsa = 78100 then 44140
when hryear4<2015 and   gtcbsa = 79600 then 49340

when hryear4>=2015 and  gtcbsa = 26180 then 46520
when hryear4>=2015 and  gtcbsa = 31100 then 31080
when hryear4>=2015 and  gtcbsa = 42060 then 42200
when hryear4>=2015 and  gtcbsa = 22460 then 22520
when hryear4>=2015 and  gtcbsa = 42260 then 35840
when hryear4>=2015 and  gtcbsa = 11300 then 26900
when hryear4>=2015 and  gtcbsa = 11340 then 24860
when hryear4>=2015 and  gtcbsa = 26100 then 24340
when hryear4>=2015 and  gtcbsa = 39100 then 35620
when hryear4>=2015 and  gtcbsa = 14060 then 14010
when hryear4>=2015 and  gtcbsa = 70750 then 12620
when hryear4>=2015 and  gtcbsa = 70900 then 12700
when hryear4>=2015 and  gtcbsa = 71650 then 14460
when hryear4>=2015 and  gtcbsa = 71950 then 14860
when hryear4>=2015 and  gtcbsa = 72400 then 15540
when hryear4>=2015 and  gtcbsa = 72850 then 14860
when hryear4>=2015 and  gtcbsa = 73450 then 25540
when hryear4>=2015 and  gtcbsa = 75700 then 35300
when hryear4>=2015 and  gtcbsa = 76450 then 35980
when hryear4>=2015 and  gtcbsa = 76750 then 38860
when hryear4>=2015 and  gtcbsa = 77200 then 39300
when hryear4>=2015 and  gtcbsa = 77350 then 14460
when hryear4>=2015 and  gtcbsa = 78100 then 44140
when hryear4>=2015 and  gtcbsa = 78700 then 35300
when hryear4>=2015 and  gtcbsa = 79600 then 49340

when hryear4>=2015 and  gestfips = 1 and gtco = 3 then 19300
when hryear4>=2015 and  gestfips = 10 and gtco = 5 then 41540
when hryear4>=2015 and  gestfips = 37 and gtco = 57 then 49180
when hryear4>=2015 and  gestfips = 37 and gtco = 97 then 16740
when hryear4>=2015 and  gestfips = 41 and gtco = 43 then 10540
when hryear4>=2015 and  gestfips = 42 and gtco = 55 then 16540
when hryear4>=2015 and  gestfips = 42 and gtco = 89 then 20700
else gtcbsa end msa13,

case 
when gtcbsa=26180 then 46520
when gtcbsa=31100 then 31080
when gtcbsa=42060 then 42200
when gtcbsa=22460 then 22520
when gtcbsa=42260 then 35840
when gtcbsa=46940 then 42680
when gtcbsa=11300 then 26900
when gtcbsa=11340 then 24860
when gtcbsa=26100 then 24340
when gtcbsa=39100 then 35620
when gtcbsa=23020 then 18880
when gtcbsa=14060 then 14010
when gtcbsa=70750 then 12620
when gtcbsa=70900 then 12700
when gtcbsa=71650 then 14460
when gtcbsa=71950 then 14860
when gtcbsa=72400 then 15540
when gtcbsa=72850 then 14860
when gtcbsa=73450 then 25540
when gtcbsa=74500 then 49340
when gtcbsa=75700 then 35300
when gtcbsa=76450 then 35980
when gtcbsa=76750 then 38860
when gtcbsa=77200 then 39300
when gtcbsa=77350 then 14460
when gtcbsa=78100 then 44140
when gtcbsa=78700 then 35300
when gtcbsa=79600 then 49340
when gestfips=1 and gtco=3 then 19300
when gestfips=4 and gtco=3 then 43420
when gestfips=4 and gtco=15 then 29420
when gestfips=10 and gtco=5 then 41540
when gestfips=37 and gtco=57 then 49180
when gestfips=37 and gtco=97 then 16740
when gestfips=41 and gtco=43 then 10540
when gestfips=42 and gtco=55 then 16540
when gestfips=42 and gtco=89 then 20700
else gtcbsa 
end msa5yr13,

case when hryear4<2015 then gtcbsa else null end msa5yr03,

case 

when 
gtcbsa in (41540,26580,14540,27140,13740,35380,25180,29180,13980,24860,37460,47380,44060,16740,44140,16060,14010,34980,28700,16820,28940,17300,17860,22900,12700,18880,32820,16620,49340,
41620,15540,47580,21780,40060,31180,24780,18140,43340,26820,19660,35620,27980,49180,19100,34820,43900,47260,12260,14460,41180,24340,30020,30340,11100,40380,26420,12060,31700,33260,26900,
21340,47900,31540,45780,35980,36260,38860,28140,17140,19380,31140,48620,39300,13140,35300,12620,25540,14860,33460,46220,25060,14020,47020)
then 1

when hryear4<2015 and gtcbsa in (14060,23020,70750,70900,71650,71950,72400,73450,75700,76450,76750,77200,78100,79600) then 1

when hryear4>=2015 and gtcbsa in (11300,11340,26100,39100,14060,70750,70900,71650,71950,72400,72850,73450,75700,76450,76750,77200,77350,78100,78700,79600) then 1


when hryear4>=2015 and ((gestfips = 10 and gtco = 5) or (gestfips = 37 and gtco = 57) or (gestfips = 37 and gtco = 97)) then 1
when hryear4>=2015 and ((gestfips = 1 and gtco = 3) or (gestfips = 41 and gtco = 43) or (gestfips = 42 and gtco = 55) or (gestfips = 42 and gtco = 89)) then 2

when gtcbsa=0 then -1
when hryear4<2015 and  gtcbsa = 11300 then -1
when hryear4<2015 and  gtcbsa = 11340 then -1
when hryear4<2015 and  gtcbsa = 26100 then -1
when hryear4<2015 and  gtcbsa = 39100 then -1
when hryear4<2015 and  gtcbsa = 72850 then -1
when hryear4<2015 and  gtcbsa = 74500 then -1
when hryear4<2015 and  gtcbsa = 77350 then -1
when hryear4<2015 and  gtcbsa = 78700 then -1

else 2 end msa13chg,



case 
      when hryear4>=2021 then null
	when hryear4>=2015 and  hunbnk=1 then 1
	when hryear4>=2015 and hunbnk=2 and 	(
huse12CC = 1 or 
		   huse12MO = 1 or 
		   huse12RM = 1 or
		   huse12PDL = 1 or 
		   huse12PWN = 1 or 
		   huse12RTO = 1 or 
		   huse12RAL = 1  )
		then 2

when  hryear4>=2015 and  hunbnk=2 and 
	(

huse12CC in (2,3) and 
		   huse12MO in (2,3) and 
		   huse12RM in (2,3) and
		   huse12PDL in (2,3) and 
		   huse12PWN in (2,3) and 
		   huse12RTO in (2,3) and 
		   huse12RAL in (2,3) 
) then 3
when hryear4>=2015 then 4 


when hryear4=2009 then null
	when hunbnk=1 then 1
	when hunbnk=2 and 	(
huse2CC = 1 or 
		   huse2MO = 1 or 
		   huse2RM = 1 or
		   huse2PDL = 1 or 
		   huse2PWN = 1 or 
		   huse2RTO = 1 or 
		   huse2RAL = 1  )
		then 2

when  hunbnk=2 and 
	(

huse2CC in (2,3) and 
		   huse2MO in (2,3) and 
		   huse2RM in (2,3) and
		   huse2PDL in (2,3) and 
		   huse2PWN in (2,3) and 
		   huse2RTO in (2,3) and 
		   huse2RAL in (2,3) 
) then 3
else 4 end hbankstatv2,





case       
      when hryear4>=2021 then null
	when hryear4>=2015 and hunbnk=1 then 1

	when hryear4>=2015 and hunbnk=2 and 	(
huse12CC = 1 or 
		   huse12MO = 1 or 
		   huse12RM = 1 or
		   huse12PDL = 1 or 
		   huse12PWN = 1 or 
		   huse12RTO = 1 or 
		   huse12RAL = 1 or 
		   huse12ATL=1
 )
		then 2

when  hryear4>=2015 and hunbnk=2 and 
	(

huse12CC in (2,3) and 
		   huse12MO in (2,3) and 
		   huse12RM in (2,3) and
		   huse12PDL in (2,3) and 
		   huse12PWN in (2,3) and 
		   huse12RTO in (2,3) and 
		   huse12RAL in (2,3) and
		   huse12ATL in (2,3)
) then 3

when hryear4>=2015 then 4


	when hryear4<2013 then null
	when hunbnk=1 then 1
	when hunbnk=2 and 	(
huse2CC = 1 or 
		   huse2MO = 1 or 
		   huse2RM = 1 or
		   huse2PDL = 1 or 
		   huse2PWN = 1 or 
		   huse2RTO = 1 or 
		   huse2RAL = 1 or 
		   huse2ATL=1
 )
		then 2

when  hunbnk=2 and 
	(

huse2CC in (2,3) and 
		   huse2MO in (2,3) and 
		   huse2RM in (2,3) and
		   huse2PDL in (2,3) and 
		   huse2PWN in (2,3) and 
		   huse2RTO in (2,3) and 
		   huse2RAL in (2,3) and
		   huse2ATL in (2,3)
) then 3
else 4 end hbankstatv3,



case 
when hryear4!=2017 then null
when hunbnk=1 then 1
when hunbnk=2 and (huse12CC=1 or huse12MO=1 or huse12RM=1 or huse12PDL=1 or huse12PWN=1 or huse12RTO=1 or huse12RAL=1 or huse12ATL=1 or huse12oafsc=1) then 2
when hunbnk=2 and (huse12CC=2 and huse12MO=2 and huse12RM=2 and huse12PDL=2 and huse12PWN=2 and huse12RTO=2 and huse12RAL=2 and huse12ATL=2 and (huse12oafsc=2 or huse12oafsc=-1)) then 3
else 4
end hbankstatv4,



case 
when hryear4>=2015 then null 
when huse1CC = 1 or huse1MO = 1 then  1
when  huse1CC = 2 and huse1MO = 2 then  2
else  99  end  huse1AFST  ,



case 
when hryear4>=2015 then null 
when hryear4=2009 then null 
when huse1CC = 1 or huse1MO = 1 or huse1RM = 1 then  1
when  huse1CC = 2 and huse1MO = 2 and huse1RM = 2 
then  2
else  99  end  huse1AFSTv2  ,


case 
when  hryear4=2009 then null
when hryear4>=2015 and (huse12CC = 1 or huse12MO = 1 ) then 1
when hryear4>=2015 and huse12CC in (2,3) and huse12MO in (2,3)  then 2
when hryear4>=2015 then 99
when huse2CC = 1 or huse2MO = 1  then  1
when  huse2CC in (2,3) and huse2MO in (2,3) then  2
else  99  end     huse2AFSTv1  ,

case 
when hryear4>=2015 then null 
when hryear4<2011 then null 
when huse2CC = 1 or huse2MO = 1 or huse2RM = 1 then  1
when  huse2CC in (2,3) and huse2MO in (2,3) and huse2RM in (2,3) 
then  2
else  99  end     huse2AFSTv2  ,


case  

when hryear4>=2015 then null 
when hryear4<2011 then null 

when huse3CC = 1 or huse3MO = 1 or huse3RM = 1 then  1
when  huse3CC in (2,3) and huse3MO in (2,3) and huse3RM in (2,3) 
then  2
else  99  end     huse3AFSTv2  ,


case   when hryear4>=2015 then null
when huse1PDL = 1 or huse1PWN = 1 or huse1RTO = 1 or huse1RAL = 1 
then  1
when  huse1PDL = 2 and huse1PWN = 2 and huse1RTO = 2 AND huse1RAL = 2 
then  2
else  99  end  huse1AFSC  ,


case 
when hryear4>=2023 then null
when hryear4>=2015 and (huse12PDL = 1 or huse12PWN = 1 or huse12RTO = 1 or huse12RAL = 1) then 1
when  hryear4>=2015 and  huse12PDL in (2,3) and huse12PWN in (2,3) and huse12RTO in (2,3) AND huse12RAL in (2,3)  then 2
when  hryear4>=2015 then 99

when hryear4<2011 then null 
when huse2PDL = 1 or huse2PWN = 1 or huse2RTO = 1 or huse2RAL = 1 
then  1
when  huse2PDL in (2,3) and huse2PWN in (2,3) and huse2RTO in (2,3) AND huse2RAL in (2,3) 
then  2
else  99  end   huse2AFSC  ,

case 

when hryear4>=2015 then null
when hryear4<2013 then null
when huse3PDL = 1 or huse3PWN = 1 or huse3RTO = 1 then  1
when  huse3PDL in (2,3) and huse3PWN in (2,3) and huse3RTO in (2,3) 
then  2
else  99  end   huse3AFSC  ,


case 
when hryear4>=2015 then null
when hryear4<2013 then null
when huse1PDL = 1 or huse1PWN = 1 or huse1RTO = 1 or huse1RAL = 1 or huse1ATL = 1
then  1
when  huse1PDL = 2 and huse1PWN = 2 and huse1RTO = 2 AND huse1RAL = 2 and huse1ATL = 2
then  2
else  99  end  huse1AFSCv2  ,

case 
when hryear4>=2015 then null

when hryear4<2013 then null
when huse2PDL = 1 or huse2PWN = 1 or huse2RTO = 1 or huse2RAL = 1  or huse2ATL = 1
then  1
when  huse2PDL in (2,3) and huse2PWN in (2,3) and huse2RTO in (2,3) AND huse2RAL in (2,3) AND huse2ATL in (2,3)
then  2
else  99  end   huse2AFSCv2  ,

case 
   when hryear4>=2015 then null
when hryear4<2013 then null
when huse3PDL = 1 or huse3PWN = 1 or huse3RTO = 1 or huse3ATL = 1 
then  1
when  huse3PDL in (2,3) and huse3PWN in (2,3) and huse3RTO in (2,3) AND huse3ATL in (2,3) 
then  2
else  99  end   huse3AFSCv2  ,



case  when hryear4>=2015 then null
when (huse1CC = 1 or huse1MO = 1) or (huse1PDL = 1 or huse1PWN = 1 or huse1RTO = 1 or huse1RAL = 1)   then  1 
when  (huse1CC = 2 and huse1MO = 2) and (huse1PDL = 2 and huse1PWN = 2 and huse1RTO = 2 AND huse1RAL = 2) then  2 
else  99  end      huse1AFS ,

case 
when hryear4>=2023 then null
when hryear4<2013 then null
when hryear4>=2019 and (hecnbpdl = 1 or hecnbpwn = 1 or hecnbtax = 1 or hecnbatl = 1 or hecnbrto = 1) then 1
when hryear4>=2019 and (hecnbpdl = 2 and hecnbpwn = 2 and hecnbtax = 2 and hecnbatl = 2 and hecnbrto = 2) then 2
when hryear4=2013 and (huse2PDL = 1 or huse2PWN = 1 or huse2RTO = 1 or huse2RAL = 1  or huse2ATL = 1) then  1
when hryear4=2013 and  huse2PDL in (2,3) and huse2PWN in (2,3) and huse2RTO in (2,3) AND huse2RAL in (2,3) AND huse2ATL in (2,3) then  2
when hryear4=2013 then 99  
when hes122 =1 or hes123 =1 or hes125 =1 or hes124 =1 or hes126 =1 then 1 when hes122 =2 and hes123 =2 and hes125 =2 and hes124 =2 and hes126 =2 then 2 else 99 end huse12AFSC,

case 
when (prdisflg = 1 or pemlr = 6) and prtage >= 25 and prtage < 65 then 1
when prtage >= 25 and  prtage < 65 and not(prdisflg = 1 or pemlr = 6) then 2
else 99 end pdisabl_age25to64

from pp_plus a')



#####################################################################################################################################
#create summary variables based on already created variables

pp_plus<-sqldf('select a.*,


case when pnativ=1 then 1 
else 2 end pnativ2,


case 
when hryear4>=2015 then null
when hryear4>=2013 and hbnkaccm5=1 and hbankstatv3=2 then 1
when hryear4>=2013 and hbnkaccm5=1 and hbankstatv3=3 then 2
when hryear4>=2013 and hbnkaccm5=1 and hbankstatv3=4 then 3
when hryear4>=2013 then -1 
else null
end hmobnk,

case 

when hryear4>=2015 then null
when hryear4>=2013 and husepp=1 and hplacepp=4 and hbankstatv3=1 then 1
when hryear4>=2013 then 2
end hbnkppunb,

case 
when hryear4>=2015 then null
when hryear4>=2013 and husepp=1 and hplacepp=4  then 1
when hryear4>=2013 then 2
end hbnkpp,



case 
when hryear4>=2015 then null
when hryear4>=2013 and husepp=1 and hbankstatv3=1 then 1
when hryear4>=2013 then 2
end hunbnkpp,

case 


      when hryear4>=2021 then null
when hryear4<2011 then null 
when hryear4>=2019 and (henbmo10 = 1 or henbcc10 = 1 or henbrm10 = 1) then 1
when hryear4>=2019 and (henbmo10 = 2 and henbcc10 = 2 and henbrm10 = 2) then 2
when hryear4 <2015 and (huse2CC = 1 or huse2MO = 1 or huse2RM = 1) then  1
when hryear4 <2015 and  huse2CC in (2,3) and huse2MO in (2,3) and huse2RM in (2,3) then  2
when hryear4 <2015 then 99  
when hes120 = 1 or hes121 = 1 or hes133 = 1 or hes1352 = 1 then 1  when hes120 =2 and hes121 =2 and ((hes133 = 2 or hes130 = 2) or (hes1352 = 2 or hes130 = 2)) then 2 else 99 end huse12AFST,

case 
      when hryear4>=2021 then null
when hryear4<2013 then null
when hryear4>=2019 and (henbmo10 = 1 or henbcc10 = 1 or henbrm10 = 1 or hecnbpdl = 1 or hecnbpwn = 1 or hecnbtax = 1 or hecnbatl = 1 or hecnbrto = 1) then 1
when hryear4>=2019 and (henbmo10 = 2 and henbcc10 = 2 and henbrm10 = 2 and hecnbpdl = 2 and hecnbpwn = 2 and hecnbtax = 2 and hecnbatl = 2 and hecnbrto = 2) then 2
when hryear4=2013 and (huse2AFSTv2 = 1 or huse2AFSCv2 = 1)   then  1 
when  hryear4=2013 and huse2AFSTv2 = 2 and huse2AFSCv2 = 2 then  2 
when hryear4=2013 then 99  
when (hes120 = 1 or hes121 = 1 or hes133 = 1 or hes1352 = 1) or (hes122 =1 or hes123 =1 or hes125 =1 or hes124 =1 or hes126 =1) then 1   when hes120 =2 and hes121 =2  and hes122 =2 and hes123 =2 and hes125 =2 and hes124 =2 and ((hes133 = 2 or hes130 = 2) or (hes1352 = 2 or hes130 = 2)) and hes126 =2  then 2
else 99 end huse12AFS ,


case 
when hryear4>=2019 then null
when hryear4<2017 then null
when hryear4>=2017 and (huse12PDL = 1 or huse12PWN = 1 or huse12RTO = 1 or huse12RAL = 1  or huse12ATL = 1 or huse12oafsc = 1) then 1
when hryear4>=2017 and (huse12PDL = 2 and huse12PWN = 2 and huse12RTO = 2 AND huse12RAL = 2 AND huse12ATL = 2 and (huse12oafsc = 2 or huse12oafsc = -1)	) then 2
	else 99 end huse12afscv2,






case 
when hryear4>=2019 then null
when hryear4<2017 then null  
when (hes120 = 1 or hes121 = 1 or hes133 = 1 or hes1352 = 1) or (hes122 =1 or hes123 =1 or hes125 =1 or hes124 =1 or hes126 =1 or huse12oafsc = 1) then 1  
when hes120 =2 and hes121 =2  and hes122 =2 and hes123 =2 and hes125 =2 and hes124 =2 and hes126 =2  and (huse12oafsc = 2 or huse12oafsc = -1) and ((hes133 = 2 or hes130 = 2) or (hes1352 = 2 or hes130 = 2)) then 2
else 99 end huse12AFSv2



from pp_plus a

')

print(names(pp_plus))
print('bbbb')
#pp_plus=subset(pp_plus,select=-
#c(hxb20           ,  hxp10        ,     hxpw10a ,          hxpw10b ,          hxpw10c  ,         hxpw10d   ,        hxpbuse,           hxub55a1   ,      
# hxub55g         ,  hxnbmo15   ,       hxnbmo16,          hxnbbp10,          hxnbbp15 ,         hxnbcc15,          hxnbrm10,          hxnbrm15 ,         hxnbp2p ,         
#  hxba10x         ,  hxbr10   ,         hxbr15 ,           hxa20   ,          hxa40    ,         hxca10,            hxca15  ,          hxca20 ,           hxs10   ,         
# hxh10             ,hxh20   ,          hxh30 ,            hxh40  ))


print('eeee')


#pp_plus_save=subset(pp_plus, select=c( hxa20, hxa40, hxh10, hxh15, hxh20, hxh30, hxh40, pehspnon, pehgcomp, pehrusl1, pehrusl2, pehrftpt,pehruslt, pehrwant, pehrrsn1, pehrrsn2, pehrrsn3, pehract1, pehract2, pehractt, pehravl))

pp_plus=pp_plus[, !grepl('pxs|filler|pea|pel|pul|hx|puh|peh|hxs',names(pp_plus)) ||
 grepl('hxa20| hxa40| hxh10| hxh15| hxh20| hxh30| hxh40| pehspnon| pehgcomp| pehrusl1|pehrusl2| pehrftpt|pehruslt| pehrwant| pehrrsn1| pehrrsn2| pehrrsn3|pehract1| pehract2| pehractt| pehravl|hxhousut|hxfaminc',names(pp_plus)) ]

 

print(names(pp_plus))
print('fff')
################################################################################################################################################
# new vars to add

	
########################################################################################################################


hhp=sqldf('select a.qstnum,a.perrp,
hagele15,hagele16,hagele17,hagele18,hagege18,hagege16,hagege15_17,hagege15_18,hagege18_24,
unbnk_yn,ptypchk_yn,ptypsav_yn,ptypunk_yn,pnum,p_hrs_wrk,p_hrs_wrk2,p_weekly_earn
,pnum_mill,pnum_mill_bnk,pnum_mill_unbnk,pnum_mill_unk,pnumlt15bnk,pnumlt15unbnk,
pnumlt15unk,pnum15_17bnk,pnum15_17chk,pnum15_17sav,pnum15_17unbnk,pnum15_17unk,pnumge18bnk,
pnumge18unbnk,pnumge18unk,hlivwfam,hlivwnonfam,hlivwfam_mill,hlivwnonfam_mill

 from pp_plus a ,  uniq_hh b,hh_variables_from_multiperson_data c
 where a.qstnum=b.qstnum and a.perrp=b.perrp and hbaseint>0 
 and a.qstnum=c.qstnum ')

hh0=sqldf('select a.*
 from pp_plus a ,uniq_hh b,hh_variables_from_multiperson_data c
 where a.qstnum=b.qstnum and a.perrp=b.perrp and hbaseint>0
 and a.qstnum=c.qstnum 

')





hh1<-sqldf('select a.qstnum,a.perrp,
case 
when hryear4>=2015 then null
when hryear4<2011 then null
when huse1AFSTv2 = 1 or huse1AFSC = 1   then  1 
when  huse1AFSTv2 = 2 and huse1AFSC = 2 then  2 
else  99  end      huse1AFSv2  ,

case 
      when hryear4>=2021 then null
when hryear4<2011 then null
when hryear4>=2015 and huse12AFST = 1 or huse2AFSC = 1   then  1 
when hryear4>=2015 and huse12AFST = 2 and huse2AFSC = 2 then  2 
when hryear4>=2015  then 99

when huse2AFSTv2 = 1 or huse2AFSC = 1   then  1 
when  huse2AFSTv2 = 2 and huse2AFSC = 2 then  2 
else  99  end      huse2AFSv2  ,

case 
when hryear4>=2015 then null
when hryear4<2013 then null
when huse3AFSTv2 = 1 or huse3AFSC = 1   then  1 
when  huse3AFSTv2 = 2 and huse3AFSC = 2 then  2 
else  99  end      huse3AFSv2  ,

case 

when hryear4>=2015 then null
when hryear4<2013 then null
when huse1AFSTv2 = 1 or huse1AFSCv2 = 1   then  1 
when  huse1AFSTv2 = 2 and huse1AFSCv2 = 2 then  2 
else  99  end      huse1AFSv3  ,

case 
when hryear4>=2015 then null
when hryear4<2013 then null
when huse2AFSTv2 = 1 or huse2AFSCv2 = 1   then  1 
when  huse2AFSTv2 = 2 and huse2AFSCv2 = 2 then  2 
else  99  end      huse2AFSv3  ,

case
when hryear4>=2015 then null
 when hryear4<2013 then null
when huse3AFSTv2 = 1 or huse3AFSCv2 = 1   then  1 
when  huse3AFSTv2 = 2 and huse3AFSCv2 = 2 then  2 
else  99  end      huse3AFSv3  ,


case 
	when hryear4>2011 then null
	when hryear4=2009 and hes12<-1 then 99
	when hryear4=2009 then hes12 
	when hryear4=2011 and hes8<-1 then 99
	when hryear4=2011 then hes8 
	end hbnkfutrrsn,

case 
	when hryear4>2009 then null
	when hes16<-1 then 99
	else hes16 end huseccrsn,

case 
	when hryear4>2009 then null
	when hes19<-1 then 99
	else hes19 end husemorsn,

case 
	when hryear4>2009 then null
	when hes22<-1 then 99
	else hes22 end husepdlrsn,

case 
	when hryear4>2009 then null
	when hes25<-1 then 99
	else hes25 end husepwnrsn,


case 
	when hryear4!=2011 then null
	when hes5<-1 then 99
	when hes5=11 then 10
	else hes5 end hunbnkrm,


case 
	when hryear4!=2011 then null
	when hes13<-1 then 99
	else hes13 end huseccrsnv2,


case 
	when hryear4!=2011 then null
	when hes19<-1 then 99
	else hes19 end husemorsnv2 ,


case 
	when hryear4!=2011 then null
	when hes18<-1 then 99
	else hes18 end huse3mopo ,



case 
	when hryear4!=2011 then null
	when hes24<-1 then 99
	else hes24 end husermrsnv2 ,



case 
	when hryear4!=2011 then null
	when hes28<-1 then 99
	else hes28 end husepdlrsnv2,

case 
	when hryear4!=2011 then null
	when hes32<-1 then 99
	else hes32 end husepwnrsnv2 ,


case 
     when hryear4>2009 then null
     when hes29<-1 then 99
     else hes29 end huseafscrsn ,

case 
	when hryear4!=2011 then null
	when hes37<-1 then 99
	else hes37 end huseafscrsnv2 ,


case 
	when hryear4!=2011 then null
	when hts12<-1 then 99
	else hts12 end huse3ccfq ,




case 
	when hryear4!=2011 then null
	when hts17<-1 then 99
	else hts17 end huse3mofq ,



case 
	when hryear4!=2011 then null
	when hts23<-1 then 99
	else hts23 end huse3rmfq ,

case 

when (hryear4<2013 or hryear4>=2019) then null 
when hunbnk=1 then null
else
case when hbnkaccm1=1 then 1 else 0 end+ 
case when hbnkaccm2=1 then 1 else 0 end+ 
case when hbnkaccm3=1 then 1 else 0 end+ 
case when hbnkaccm4=1 then 1 else 0 end+ 
case when hbnkaccm5=1 then 1 else 0 end+ 
case when hbnkaccm6=1 then 1 else 0 end
end
hnumbmths_c


from hh0 a')



hh1=sqldf('select b.*,

case 
when hryear4>=2021 then null
when hryear4<2011 then null
when huse12AFST=1 and huse2AFSC=2 then 1
when huse12AFST=1 and huse2AFSC=1 then 2
when huse12AFST=2 and huse2AFSC=1 then 3
when huse12AFST=2 and huse2AFSC=2 then 4
when huse12AFST=1 or huse2AFSC=1 then 98
else 99 end huse2afstype,

case 
when hryear4<=2011 then null

when hryear4>=2015 then null
when huse2AFSTv2=1 and huse2AFSCv2=2 then 1
when huse2AFSTv2=1 and huse2AFSCv2=1 then 2
when huse2AFSTv2=2 and huse2AFSCv2=1 then 3
when huse2AFSTv2=2 and huse2AFSCv2=2 then 4
when huse2AFSTv2=1 or huse2AFSCv2=1 then 98
else 99 end huse2afstypev2,

case 
      when hryear4>=2021 then null
when hryear4<2013 then null
when hryear4>=2015 and huse12AFST=1 and huse12AFSC=2 then 1
when hryear4>=2015 and huse12AFST=1 and huse12AFSC=2 then 1
when hryear4>=2015 and huse12AFST=1 and huse12AFSC=1 then 2
when hryear4>=2015 and huse12AFST=2 and huse12AFSC=1 then 3
when hryear4>=2015 and huse12AFST=2 and huse12AFSC=2 then 4
when hryear4>=2015 and (huse12AFST=1 or huse12AFSC=1) then 98
when hryear4>=2015 then 99 
when hryear4=2013 and huse2AFSTv2=1 and huse2AFSCv2=2 then 1
when hryear4=2013 and huse2AFSTv2=1 and huse2AFSCv2=1 then 2
when hryear4=2013 and huse2AFSTv2=2 and huse2AFSCv2=1 then 3
when hryear4=2013 and huse2AFSTv2=2 and huse2AFSCv2=2 then 4
when hryear4=2013 and huse2AFSTv2=1 or huse2AFSCv2=1 then 98
else 99 end huse12afstype,


case 
when (hryear4<2017 or hryear4>=2019) then null
when hryear4>=2017 and huse12AFST=1 and huse12AFSCv2=2 then 1
when hryear4>=2017 and huse12AFST=1 and huse12AFSCv2=2 then 1
when hryear4>=2017 and huse12AFST=1 and huse12AFSCv2=1 then 2
when hryear4>=2017 and huse12AFST=2 and huse12AFSCv2=1 then 3
when hryear4>=2017 and huse12AFST=2 and huse12AFSCv2=2 then 4
when hryear4>=2017 and (huse12AFST=1 or huse12AFSCv2=1) then 98
when hryear4>=2017 then 99  end huse12afstypev2,





case 
when hryear4 <= 2011 then null
when hryear4>=2015 then null
when huse3AFSTv2=1 and huse3AFSCv2=2 then 1
when huse3AFSTv2=1 and huse3AFSCv2=1 then 2
when huse3AFSTv2=2 and huse3AFSCv2=1 then 3
when huse3AFSTv2=2 and huse3AFSCv2=2 then 4
when huse3AFSTv2=1 or  huse3AFSCv2=1 then 98
else 99 end huse3afstypev2,

case 
when hryear4 <= 2011 then null 
when hryear4>=2015 then null
when huse3AFSv3=1 then 1
when huse2AFSv3=1 then 2
when huse1AFSv3=1 then 3
when huse3AFSv3=2 and huse2AFSv3=2 and huse1AFSv3=2 then 4
else 99 end hanyafsv3,


case 
when hryear4>=2015 then null
when hryear4<2013 then null
when hes2=1 and hes2e<=-1 then -1
when hes2=2 and (hes3<=-1 or (hes3=1 and hes4<=-1)) then -1
when hevent1=99 or hevent2=99 or hevent3=99 or hevent4=99
or hevent5=99 or hevent6=99 or hevent7=99 or hevent8=99
or hevent9=99 or hevent10=99 or hevent11=99 then -1

when hevent1bo=99 or hevent2bo=99 or hevent3bo=99 or hevent4bo=99
or hevent5bo=99 or hevent6bo=99 or hevent7bo=99 or hevent8bo=99
or hevent9bo=99 or hevent10bo=99 or hevent11bo=99 then -1

when hevent1bc=99 or hevent2bc=99 or hevent3bc=99 or hevent4bc=99
or hevent5bc=99 or hevent6bc=99 or hevent7bc=99 or hevent8bc=99
or hevent9bc=99 or hevent10bc=99 or hevent11bc=99 then -1

when hes2=2 and hes4!=1 then 1
when hes2=2 and hes4=1 then 2
when hes2=1 and hes2e=1 then 3
when hes2=1 and hes2e!=1 then 4 end hbnktrans,



case 
when (hryear4 < 2013 or hryear4 = 2019 or hryear4 = 2021) then null
when (hryear4 >= 2023) and (heub10 = 2 or heub15 = 2) then 1
when (hryear4 >= 2023) and heub15 = 1 then 2
when (hryear4 >= 2023) and heb40 = 1 then 3
when (hryear4 >= 2023) and heb40 = 2 then 4
when (hryear4 >= 2013 and hryear4 <= 2017) and (hes3 = 2 or hes4 = 2) then 1
when (hryear4 >= 2013 and hryear4 <= 2017) and hes4 = 1 then 2
when (hryear4 >= 2013 and hryear4 <= 2017) and hes2e = 1 then 3
when (hryear4 >= 2013 and hryear4 <= 2017) and hes2e = 2 then 4
end hbnktransv2


from hh0 a, hh1 b where a.qstnum=b.qstnum and a.perrp=b.perrp')

print(names(hh1))
print('cccccccc')

#######

# added 2009 and 2011 and afs counts to 2013 july 8 2014
########################################################################################################################
hh2<-sqldf('select a.qstnum,a.perrp,

   case 
when hryear4<2017 then null 
when hryear4 >= 2021 then null 
when hryear4>=2019 and (heba10a = 1 or hebr10 = 1) then 1
when hryear4>=2019 and hebr10 = 2 then 2
when hes2g1=1 or hes70=1 then 1
when hes70=2 then 2
else -1 end hbnkbrgo,

case
when hryear4<2017 then null  
when hryear4 >= 2021 then null  
when hryear4>=2019 and (hebr15 >= 1 and hebr15 <= 3) then hebr15
when hryear4>=2019 and hebr10 = 2 then 5
when hes71>=1 and hes71<=3 then hes71
when (hes2g1=1 or hes70=1) then 4
when hes70=2 then 5
else -1 end hbnkbrgofq,

case
when hryear4<2017 then null 
when hryear4 >= 2021 then null 
when hryear4>=2019 and hebr10 = 2 then -1
when hryear4>=2019 and (hebr15>=1 and hebr15<=3) then hebr15
when not(hes2g1 = 1 or hes70 = 1) then -1
when hes71>=1 and hes71<=3 then hes71
else 4 end hbnkbrgofq_c ,

case when hes140a = 3 then -1 when hes140a < -1 then -1   else hes140a end htypincchkmo ,

case  when hryear4 <= 2013 then null when hes140a = 3 then -1 when (hes2 = 2 and (hes3 = 2 or  hes4 = 2)) then 2 when hes2=2 and (hes3 < 0 or  (hes3 = 1 and hes4 < 0))  then 2 when hes140b <= -1 then -1 else hes140b end htypincddbnk ,



case when hryear4<2015 then null when hes140a = 3 then -1 when hes140c = 1 then 1 when (hes140c = 2 or hes110 = 2) then 2 end htypincddpp,



case when hes140a = 3 then -1 when hes140d <= -1 then -1 else hes140d end htypinccash ,

case when hryear4<2015 then null when hes140a = 3 then -1 when hes140e = 1 then 1 when hes140e = 2 then 2 end htypincoth,
case when (hryear4 <= 2013 or  hryear4 >= 2019) then null when hes140a = 3 then -1 when hes120 = 2 or hes140a = 2 or hes141 = 2 then 2 when hes141=1 then 1 else -1  end htypinccc ,

case when hryear4<2017 then null when hes140x<-1 or hes140x=2 then -1 when hes140a = 3 then -1 when hes140a < -1 then -1   else hes140a end htypincchkmov2,
case when hryear4<2017 then null when hes140x<-1 or hes140x=2 then -1 when hes140a = 3 then -1 when (hes2 = 2 and (hes3 = 2 or  hes4 = 2)) then 2 when hes2=2 and (hes3 < 0 or  (hes3 = 1 and hes4 < 0))  then 2 when hes140b <= -1 then -1 else hes140b end htypincddbnkv2 ,
case 
when (hryear4<2013 or hryear4>=2019) then null 
when hbnkaccm7=2 and hnumbmths_c=1 and hbnkaccm1=1 then 1
when hbnkaccm7=2 and hnumbmths_c>1 and hbnkaccm1=1 then 2
when hbnkaccm1=2 and hbnkaccm7=2 then 3
else -1 
end hbranchstat


from hh0 a,hh1 b where  b.qstnum=a.qstnum and a.perrp=a.perrp')


print('dddddd')

#collaps to hh
hh3<-sqldf('select a.qstnum,a.perrp,

case when hryear4<2017 then null when hes140x<-1 or hes140x=2 then -1 
	when (hes140c >= -9 and hes140c <= -2 and not(hbnkprevly != 1 and hunbnk = 1 and huse12pp = 1) ) or hes140a = 3 or hes110 < -1 then -1
	when hryear4>=2017 and (hes140c<= -2 or hes110<= -2 or hes140a=3) then -1
	when hes140c = 1 then 1
	when hes140c = 2 or  (hes110 = 2 and hes140a != 3) then 2
end htypincddppv2,

case when hryear4<2017 then null when hes140x<-1 or hes140x=2 then -1  when hes140a = 3 then -1 when hes140d <= -1 then -1 else hes140d end htypinccashv2 ,

case when hryear4<2017 then null when hes140x<-1 or hes140x=2 then -1  
	when hes140e=1 then 1
	when hes140e=2 then 2
	when hes140e<0 then -1 end htypincothv2,
case when hryear4<2017 then null when hryear4 >= 2019 then null when hes140x<-1 or hes140x=2 then -1   when hes140a = 3 then -1 when hes120 = 2 or hes140a = 2 or hes141 = 2 then 2 when hes141=1 then 1 else -1  end htypincccv2 ,


case when hes150a = 3 then -1  when hes150a <= -1 then -1 else hes150a end htyppaycash ,

case when hryear4 <= 2013 then null when hes150a = 3 then -1 when hes150b = 2 or (hes2 = 2 and (hes3 = 2 or  hes4 = 2)) then 2  when hes2=2 and (hes3 < 0 or  (hes3 = 1 and hes4 < 0))  then 2  when hes150b <= -1 then -1 else hes150b end htyppaybnkchk ,


case when hryear4 <= 2013 then null when hes150a = 3  then -1 when (hes2 = 2 and (hes3 = 2 or  hes4 = 2)) then 2  when hes2=2 and (hes3 < 0 or  (hes3 = 1 and hes4 < 0))  then 2  when hes150c <= -1 then -1 else hes150c end htyppaybnkdc ,
case when hryear4 <= 2013 then null when hes150a = 3 then -1 when (hes2 = 2 and (hes3 = 2 or  hes4 = 2)) then 2  when hes2=2 and (hes3 < 0 or  (hes3 = 1 and hes4 < 0))  then 2  when hes150f <= - 1 then -1 else hes150f end htyppaybnkbp ,
case when hes150a = 3  then -1 when hes150d <= -1 then -1 else hes150d end htyppaycc ,
case when hes150a = 3 then -1 when hes110 = 2 then 2 when hes150e <= - 1 then -1 else hes150e end htyppaypp ,
case when hes150a = 3 then -1 when hes121 = 2 then 2 when hes150g <= - 1 then -1 else hes150g end htyppaynbnkmo ,
case when hes150a = 3 then -1  when hes150h <= - 1 then -1 else hes150h end htyppaybnkmo ,
case when hes150a = 3 then -1  when hes150i<= - 1 then -1 else hes150i end htyppayoth ,


case when hryear4<2017 then null when hes150x < -1 or hes150x=2 then -1 when hes150a = 3 then -1  when hes150a <= -1 then -1 else hes150a end htyppaycashv2 ,
case when hryear4<2017 then null when hes150x < -1 or hes150x=2 then -1   when hes150a = 3 then -1 when hes150b = 2 or (hes2 = 2 and (hes3 = 2 or  hes4 = 2)) then 2  when hes2=2 and (hes3 < 0 or  (hes3 = 1 and hes4 < 0))  then 2  when hes150b <= -1 then -1 else hes150b end htyppaybnkchkv2 ,
case when hryear4<2017 then null when hes150x < -1 or hes150x=2 then -1   when hes150a = 3  then -1 when (hes2 = 2 and (hes3 = 2 or  hes4 = 2)) then 2  when hes2=2 and (hes3 < 0 or  (hes3 = 1 and hes4 < 0))  then 2  when hes150c <= -1 then -1 else hes150c end htyppaybnkdcv2 ,
case when hryear4<2017 then null when hes150x < -1 or hes150x=2 then -1   when hes150a = 3 then -1 when (hes2 = 2 and (hes3 = 2 or  hes4 = 2)) then 2  when hes2=2 and (hes3 < 0 or  (hes3 = 1 and hes4 < 0))  then 2  when hes150f <= - 1 then -1 else hes150f end htyppaybnkbpv2 ,
case when hryear4<2017 then null when hes150x < -1 or hes150x=2 then -1   when hes150a = 3  then -1 when hes150d <= -1 then -1 else hes150d end htyppayccv2 ,
case when hryear4<2017 then null when hes150x < -1 or hes150x=2 then -1   when hes150a = 3 then -1 when hes110 = 2 then 2 when hes150e <= - 1 then -1 else hes150e end htyppayppv2 ,
case when hryear4<2017 then null when hes150x < -1 or hes150x=2 then -1   when hes150a = 3 then -1 when hes121 = 2 then 2 when hes150g <= - 1 then -1 else hes150g end htyppaynbnkmov2 ,
case when hryear4<2017 then null when hes150x < -1 or hes150x=2 then -1   when hes150a = 3 then -1  when hes150h <= - 1 then -1 else hes150h end htyppaybnkmov2 ,
case when hryear4<2017 then null when hes150x < -1 or hes150x=2 then -1   when hes150a = 3 then -1  when hes150i<= - 1 then -1 else hes150i end htyppayothv2 ,

case 
when hryear4 <= 2013 then null 
when hryear4>=2017 then null

 when hes151 < -1 or (hes150a != 3 and (hes150a = 2 or hes150a = -1)
	 and (hes150b = 2 or hes150b = -1) and (hes150c = 2 or hes150c = -1) and (hes150d = 2 or  hes150d = -1) 
	and (hes150e = 2 or hes150e = -1) and (hes150f = 2 or hes150f = -1) and (hes150g = 2 or hes150g = -1) and (hes150h = 2 or hes150h = -1) and (hes150i = 2 or hes150i = -1) )  then 98

	when hes151 >= 1 and hes151 <= 9 then hes151
	else -1 end

htyppaym ,

case 
	when hryear4 >= 2019 then null
	when hryear4=2009 then null
     when ptypchk_yn = 1 	   then 1
	when hes2 = 1 and ptypchk_yn =0 and ptypsav_yn =0 then 99
	when ptypunk_yn = 1 then 99
	else 2 end hhaschk ,

	case 
	when hryear4 >= 2019 then null
	when hryear4=2009 then null
      when ptypsav_yn = 1 	   then  1
	when hes2 = 1 and ptypsav_yn =0 and ptypchk_yn =0 then 99
	when ptypunk_yn = 1 then 99
	else 2 end hhassav 



 


 from hh2 a , hh0 b, hh1 c, hhp e
 where a.qstnum=b.qstnum and a.perrp=b.perrp 
 and a.qstnum=c.qstnum and a.perrp=c.perrp and a.qstnum=e.qstnum and a.perrp=e.perrp

')



foo=join(hh3,hh0)
foo=join(foo,hh1)
foo=join(foo,hh2)
foo=join(foo,hhp)

print(dim(foo))
hh4=sqldf('select a.qstnum,a.perrp
,
case 
            when hryear4>=2021 then null
	when hryear4>=2015 and (huse12cc = 99 or huse12mo = 99 or huse12rm = 99 or huse12pdl = 99 or huse12pwn = 99 or huse12ral = 99 or huse12rto = 99 ) then 99
	when hryear4>=2015 and
		(case when huse12cc=1 then 1 else 0 end+
		case when huse12mo=1 then 1 else 0 end+
		case when huse12rm=1 then 1 else 0 end+
		case when huse12pdl=1 then 1 else 0 end+
		case when huse12pwn=1 then 1 else 0 end+
		case when huse12ral=1 then 1 else 0 end+
		case when huse12rto=1 then 1 else 0 end)>3 then 3
	when hryear4>=2015 then
		case when huse12cc=1 then 1 else 0 end+
		case when huse12mo=1 then 1 else 0 end+
		case when huse12rm=1 then 1 else 0 end+
		case when huse12pdl=1 then 1 else 0 end+
		case when huse12pwn=1 then 1 else 0 end+
		case when huse12ral=1 then 1 else 0 end+
		case when huse12rto=1 then 1 else 0 end

	when hryear4=2009 then null
	when hryear4>=2011 and (huse2cc = 99 or huse2mo = 99 or huse2rm = 99 or huse2pdl = 99 or huse2pwn = 99 or huse2ral = 99 or huse2rto = 99 ) then 99
	when hryear4>=2011 and
		(case when huse2cc=1 then 1 else 0 end+
		case when huse2mo=1 then 1 else 0 end+
		case when huse2rm=1 then 1 else 0 end+
		case when huse2pdl=1 then 1 else 0 end+
		case when huse2pwn=1 then 1 else 0 end+
		case when huse2ral=1 then 1 else 0 end+
		case when huse2rto=1 then 1 else 0 end)>3 then 3
	else
		case when huse2cc=1 then 1 else 0 end+
		case when huse2mo=1 then 1 else 0 end+
		case when huse2rm=1 then 1 else 0 end+
		case when huse2pdl=1 then 1 else 0 end+
		case when huse2pwn=1 then 1 else 0 end+
		case when huse2ral=1 then 1 else 0 end+
		case when huse2rto=1 then 1 else 0 end
	end huse2afsnbr,


case 
           when hryear4>=2021 then null
	when hryear4>=2015 then null
	when hryear4=2011 then null

	when hryear4=2009 then null
	when hryear4=2013 and (huse2cc = 99 or huse2mo = 99 or huse2rm = 99 or huse2pdl = 99 or huse2pwn = 99 or huse2ral = 99 or huse2rto = 99 or huse2atl=99 ) then 99

	when hryear4=2013 and 
		(case when huse2cc=1 then 1 else 0 end+
		case when huse2mo=1 then 1 else 0 end+
		case when huse2rm=1 then 1 else 0 end+
		case when huse2pdl=1 then 1 else 0 end+
		case when huse2pwn=1 then 1 else 0 end+
		case when huse2ral=1 then 1 else 0 end+
		case when huse2rto=1 then 1 else 0 end+
		case when huse2atl=1 then 1 else 0 end
		)>3 then 3 
	else
		case when huse2cc=1 then 1 else 0 end+
		case when huse2mo=1 then 1 else 0 end+
		case when huse2rm=1 then 1 else 0 end+
		case when huse2pdl=1 then 1 else 0 end+
		case when huse2pwn=1 then 1 else 0 end+
		case when huse2ral=1 then 1 else 0 end+
		case when huse2rto=1 then 1 else 0 end+
		case when huse2atl=1 then 1 else 0 end	
	end huse2afsnbrv2,


case 
      when hryear4>=2021 then null
	when hryear4>=2015 and (huse12cc = 99 or huse12mo = 99 or huse12rm = 99 or huse12pdl = 99 or huse12pwn = 99 or huse12ral = 99 or huse12rto = 99 or huse12atl=99) then 99
	when hryear4>=2015 and
		(case when huse12cc=1 then 1 else 0 end+
		case when huse12mo=1 then 1 else 0 end+
		case when huse12rm=1 then 1 else 0 end+
		case when huse12pdl=1 then 1 else 0 end+
		case when huse12pwn=1 then 1 else 0 end+
		case when huse12ral=1 then 1 else 0 end+
		case when huse12atl=1 then 1 else 0 end+
		case when huse12rto=1 then 1 else 0 end)>3 then 3
	when hryear4>=2015 then
		case when huse12cc=1 then 1 else 0 end+
		case when huse12mo=1 then 1 else 0 end+
		case when huse12rm=1 then 1 else 0 end+
		case when huse12pdl=1 then 1 else 0 end+
		case when huse12pwn=1 then 1 else 0 end+
		case when huse12ral=1 then 1 else 0 end+
		case when huse12atl=1 then 1 else 0 end+
		case when huse12rto=1 then 1 else 0 end

	when hryear4=2009 then null
	when hryear4=2011 then null
        
	when hryear4=2013 and (huse2cc = 99 or huse2mo = 99 or huse2rm = 99 or huse2pdl = 99 or huse2pwn = 99 or huse2ral = 99 or huse2rto = 99 or huse2atl=99 ) then 99

	when hryear4=2013 and 
		(case when huse2cc=1 then 1 else 0 end+
		case when huse2mo=1 then 1 else 0 end+
		case when huse2rm=1 then 1 else 0 end+
		case when huse2pdl=1 then 1 else 0 end+
		case when huse2pwn=1 then 1 else 0 end+
		case when huse2ral=1 then 1 else 0 end+
		case when huse2rto=1 then 1 else 0 end+
		case when huse2atl=1 then 1 else 0 end
		)>3 then 3 
	else
		case when huse2cc=1 then 1 else 0 end+
		case when huse2mo=1 then 1 else 0 end+
		case when huse2rm=1 then 1 else 0 end+
		case when huse2pdl=1 then 1 else 0 end+
		case when huse2pwn=1 then 1 else 0 end+
		case when huse2ral=1 then 1 else 0 end+
		case when huse2rto=1 then 1 else 0 end+
		case when huse2atl=1 then 1 else 0 end	
	end huse12afsnbr,


case 

	when (hryear4<2017 or hryear4>=2019) then null
	when hryear4>=2017 and (huse12cc = 99 or huse12mo = 99 or huse12rm = 99 or huse12pdl = 99 or huse12pwn = 99 or huse12ral = 99 or huse12rto = 99 or huse12atl=99 or huse12oafsc = 99) then 99
	when hryear4>=2017 and
		(case when huse12cc=1 then 1 else 0 end+
		case when huse12mo=1 then 1 else 0 end+
		case when huse12rm=1 then 1 else 0 end+
		case when huse12pdl=1 then 1 else 0 end+
		case when huse12pwn=1 then 1 else 0 end+
		case when huse12ral=1 then 1 else 0 end+
		case when huse12atl=1 then 1 else 0 end+
		case when huse12rto=1 then 1 else 0 end+
	case when huse12oafsc = 1 then 1 else 0 end

)>3 then 3
	when hryear4>=2017 then
		case when huse12cc=1 then 1 else 0 end+
		case when huse12mo=1 then 1 else 0 end+
		case when huse12rm=1 then 1 else 0 end+
		case when huse12pdl=1 then 1 else 0 end+
		case when huse12pwn=1 then 1 else 0 end+
		case when huse12ral=1 then 1 else 0 end+
		case when huse12atl=1 then 1 else 0 end+
		case when huse12rto=1 then 1 else 0 end+
	case when huse12oafsc = 1 then 1 else 0 end
	
	end huse12afsnbrv2,


case 
when (hryear4<2013 or hryear4>=2019) then null 
when hunbnk=1 then -1
when 
case when hbnkaccm1=1 then 1 else 0 end+ 
case when hbnkaccm2=1 then 1 else 0 end+ 
case when hbnkaccm3=1 then 1 else 0 end+ 
case when hbnkaccm4=1 then 1 else 0 end+ 
case when hbnkaccm5=1 then 1 else 0 end+ 
case when hbnkaccm6=1 then 1 else 0 end
=0 then 0

when 
case when hbnkaccm1=1 then 1 else 0 end+ 
case when hbnkaccm2=1 then 1 else 0 end+ 
case when hbnkaccm3=1 then 1 else 0 end+ 
case when hbnkaccm4=1 then 1 else 0 end+ 
case when hbnkaccm5=1 then 1 else 0 end+ 
case when hbnkaccm6=1 then 1 else 0 end
=1 then 1
when 
case when hbnkaccm1=1 then 1 else 0 end+ 
case when hbnkaccm2=1 then 1 else 0 end+ 
case when hbnkaccm3=1 then 1 else 0 end+ 
case when hbnkaccm4=1 then 1 else 0 end+ 
case when hbnkaccm5=1 then 1 else 0 end+ 
case when hbnkaccm6=1 then 1 else 0 end
>1 then 2
else 99 end hbnkaccmnbr

,

case
when hryear4<2015 then null
when hryear4=2017 then null
when hryear4=2015 and (hcred12ccorbnk=-1 or huse12afsc=99 or hcred12newapp=-1 or hcred12denied=-1 or hcred12discour=-1 or hbilldq=99  or hcred12cc=-1 or hcred12bnk=-1) then -1
when hcred12ccorbnk=1 and huse12afsc=2 then 1
when hcred12ccorbnk=1 and huse12afsc=1 then 2
when hcred12ccorbnk=2 and huse12afsc=1 then 3
when hcred12ccorbnk=2 and huse12afsc=2 then 4 
end hcred12grps,




case 
when hryear4 >= 2019 then null
when hryear4=2009 then null
when unbnk_yn = 1   then  1 
when  ptypchk_yn = 1 and ptypsav_yn = 1 then  2 
when  ptypunk_yn = 1   then  99 
when  ptypchk_yn = 0 and ptypsav_yn = 1 then  3 
when  ptypchk_yn = 1 and ptypsav_yn = 0 then  4 
else  99  end    hbnktyp  ,


case 
when hryear4 >= 2019 then null
when hryear4=2009 then null
when unbnk_yn = 1   then  -1 
when  ptypchk_yn = 1 and ptypsav_yn = 1 then  2 
when  ptypunk_yn = 1   then  -1 
when  ptypchk_yn = 0 and ptypsav_yn = 1 then  3 
when  ptypchk_yn = 1 and ptypsav_yn = 0 then  4 
else  -1  end    hbnktypc  ,


case when hryear4<2015 then null  
when hryear4 >= 2019 then null 
when huse12pp=99 or huse12cc=99 or huse12mo=99 or hes140a=3 or hes150a=3 or hes150a< -1 or hes150b< -1 or hes150c< -1 or hes150d< -1 or hes150e< -1 or hes150f< -1 or hes150g< -1 or hes150h< -1 or hes150i< -1
   or hes140a<-1 or hes140b< -1 or hes140d< -1 or hes140e < -1 or (hryear4=2015 and hes140c< -1 and not (hbnkprevly>1 and huse12pp=1)) then -1
	when hryear4>=2017 and (hes140c <= -2 or hes141 <= -2) then -1
  when hes140a=1 or hes140b=1 or hes140c=1 or hes140d=1 or hes140e=1 then 2
   else 1 end htypincnone,

case when hryear4<2015 then null 
when hryear4 >= 2019 then null   when huse12pp=99 or huse12cc=99 or huse12mo=99 or hes140a=3 or hes150a=3 or hes150a< -1 or hes150b< -1 or hes150c< -1 or hes150d< -1 or hes150e< -1 or hes150f< -1 or hes150g< -1 or hes150h< -1 or hes150i< -1
   or hes140a<-1 or hes140b< -1 or hes140d< -1 or hes140e < -1 or (hryear4=2015 and hes140c< -1 and not (hbnkprevly>1 and huse12pp=1)) then -1
	when hryear4>=2017 and (hes140c <= -2 or hes141 <= -2) then -1
	when htypincddbnk=1 or (htypincchkmo=1 and hunbnk=2 and htypinccc=2) then 1
	else 2 end htypincbnka,

case when hryear4<2015 then null
when hryear4 >= 2019 then null   when huse12pp=99 or huse12cc=99 or huse12mo=99 or hes140a=3 or hes150a=3 or hes150a< -1 or hes150b< -1 or hes150c< -1 or hes150d< -1 or hes150e< -1 or hes150f< -1 or hes150g< -1 or hes150h< -1 or hes150i< -1
   or hes140a<-1 or hes140b< -1 or hes140d< -1 or hes140e < -1 or (hryear4=2015 and hes140c< -1 and not (hbnkprevly>1 and huse12pp=1)) then -1
	when hryear4>=2017 and (hes140c <= -2 or hes141 <= -2) then -1
	when hes140c = 1 or hes140d = 1 or hes140e = 1 or hes141 = 1 then 2 
	when htypincddbnk=1 or (htypincchkmo=1 and hunbnk=2 and htypinccc=2) then 1
	else 2 end  htypincbnko,


case when hryear4<2015 then null  
when hryear4 >= 2019 then null 
 when huse12pp=99 or huse12cc=99 or huse12mo=99 or hes140a=3 or hes150a=3 or hes150a< -1 or hes150b< -1 or hes150c< -1 or hes150d< -1 or hes150e< -1 or hes150f< -1 or hes150g< -1 or hes150h< -1 or hes150i< -1
   or hes140a<-1 or hes140b< -1 or hes140d< -1 or hes140e < -1 or (hryear4=2015 and hes140c< -1 and not (hbnkprevly>1 and huse12pp=1)) then -1
	when hryear4>=2017 and (hes140c <= -2 or hes141 <= -2) then -1
  when hes150a=1 or hes150b=1 or hes150c=1 or hes150d=1 or hes150e=1 or hes150f=1 or hes150g=1 or hes150h=1 or hes150i=1 then 2
   else 1 end htyppaynone,


case when hryear4<2015 then null 
when hryear4 >= 2019 then null 
  when huse12pp=99 or huse12cc=99 or huse12mo=99 or hes140a=3 or hes150a=3 or hes150a< -1 or hes150b< -1 or hes150c< -1 or hes150d< -1 or hes150e< -1 or hes150f< -1 or hes150g< -1 or hes150h< -1 or hes150i< -1
   or hes140a<-1 or hes140b< -1 or hes140d< -1 or hes140e < -1 or (hryear4=2015 and hes140c< -1 and not (hbnkprevly>1 and huse12pp=1)) then -1
	when hryear4>=2017 and (hes140c <= -2 or hes141 <= -2) then -1
   when htyppaybnkbp=1 or htyppaybnkchk=1 or htyppaybnkdc=1 or htyppaycc=1 or htyppaybnkmo=1 then 1
   else 2 end htyppaybnka,

case when hryear4<2015 then null 
when hryear4 >= 2019 then null 
  when huse12pp=99 or huse12cc=99 or huse12mo=99 or hes140a=3 or hes150a=3 or hes150a< -1 or hes150b< -1 or hes150c< -1 or hes150d< -1 or hes150e< -1 or hes150f< -1 or hes150g< -1 or hes150h< -1 or hes150i< -1
   or hes140a<-1 or hes140b< -1 or hes140d< -1 or hes140e < -1 or (hryear4=2015 and hes140c< -1 and not (hbnkprevly>1 and huse12pp=1)) then -1
	when hryear4>=2017 and (hes140c <= -2 or hes141 <= -2) then -1
   when (htyppaybnkbp=1 or htyppaybnkchk=1 or htyppaybnkdc=1 or htyppaycc=1 or htyppaybnkmo=1) and htyppaycash=2 and htyppaypp=2 and htyppaynbnkmo=2 and htyppayoth=2 then 1
   else 2 end htyppaybnko,

case 
 when hryear4<2015 then null  
when hryear4 >= 2019 then null
when huse12pp=99 or huse12cc=99 or huse12mo=99 or hes140a=3 or hes150a=3 or hes150a< -1 or hes150b< -1 or hes150c< -1 or hes150d< -1 or hes150e< -1 or hes150f< -1 or hes150g< -1 or hes150h< -1 or hes150i< -1
   or hes140a<-1 or hes140b< -1 or hes140d< -1 or hes140e < -1 or (hryear4=2015 and hes140c< -1 and not (hbnkprevly>1 and huse12pp=1)) then -1 
	when hryear4>=2017 and (hes140c <= -2 or hes141 <= -2) then -1
when hunbnk=1 then -1

when  (not (hes140c = 1 or hes140d = 1 or hes140e = 1 or hes141 = 1) and   (htypincddbnk=1 or (htypincchkmo=1 and hunbnk=2 and htypinccc=2) ))
 and ((htyppaybnkbp=1 or htyppaybnkchk=1 or htyppaybnkdc=1 or htyppaycc=1 or htyppaybnkmo=1) and htyppaycash=2 and htyppaypp=2 and htyppaynbnkmo=2 and htyppayoth=2) then 1 else 2 end htypbnko,


case when hryear4<2017 then null when hryear4 >= 2019 then null when hes140x < -1 or hes140x=2 or hes150x < -1 or hes150x=2 then -1 when huse12pp=99 or huse12cc=99 or huse12mo=99 or hes140a=3 or hes150a=3 or hes150a< -1 or hes150b< -1 or hes150c< -1 or hes150d< -1 or hes150e< -1 or hes150f< -1 or hes150g< -1 or hes150h< -1 or hes150i< -1
   or hes140a<-1 or hes140b< -1 or hes140d< -1 or hes140e < -1 or (hryear4=2015 and hes140c< -1 and not (hbnkprevly>1 and huse12pp=1)) then -1
	when hryear4>=2017 and (hes140c <= -2 or hes141 <= -2) then -1
  when hes140a=1 or hes140b=1 or hes140c=1 or hes140d=1 or hes140e=1 then 2
   else 1 end htypincnonev2,

case when hryear4<2017 then null when hryear4 >= 2019 then null  when hes140x < -1 or hes140x=2 or hes150x < -1 or hes150x=2 then -1  when huse12pp=99 or huse12cc=99 or huse12mo=99 or hes140a=3 or hes150a=3 or hes150a< -1 or hes150b< -1 or hes150c< -1 or hes150d< -1 or hes150e< -1 or hes150f< -1 or hes150g< -1 or hes150h< -1 or hes150i< -1
   or hes140a<-1 or hes140b< -1 or hes140d< -1 or hes140e < -1 or (hryear4=2015 and hes140c< -1 and not (hbnkprevly>1 and huse12pp=1)) then -1
	when hryear4>=2017 and (hes140c <= -2 or hes141 <= -2) then -1
	when htypincddbnk=1 or (htypincchkmo=1 and hunbnk=2 and htypinccc=2) then 1
	else 2 end htypincbnkav2,

case when hryear4<2017 then null when hryear4 >= 2019 then null when hes140x < -1 or hes140x=2 or hes150x < -1 or hes150x=2 then -1  when huse12pp=99 or huse12cc=99 or huse12mo=99 or hes140a=3 or hes150a=3 or hes150a< -1 or hes150b< -1 or hes150c< -1 or hes150d< -1 or hes150e< -1 or hes150f< -1 or hes150g< -1 or hes150h< -1 or hes150i< -1
   or hes140a<-1 or hes140b< -1 or hes140d< -1 or hes140e < -1 or (hryear4=2015 and hes140c< -1 and not (hbnkprevly>1 and huse12pp=1)) then -1
	when hryear4>=2017 and (hes140c <= -2 or hes141 <= -2) then -1
	when hes140c = 1 or hes140d = 1 or hes140e = 1 or hes141 = 1 then 2 
	when htypincddbnk=1 or (htypincchkmo=1 and hunbnk=2 and htypinccc=2) then 1
	else 2 end  htypincbnkov2,


case when hryear4<2017 then null when hryear4 >= 2019 then null  when hes140x < -1 or hes140x=2 or hes150x < -1 or hes150x=2 then -1  when huse12pp=99 or huse12cc=99 or huse12mo=99 or hes140a=3 or hes150a=3 or hes150a< -1 or hes150b< -1 or hes150c< -1 or hes150d< -1 or hes150e< -1 or hes150f< -1 or hes150g< -1 or hes150h< -1 or hes150i< -1
   or hes140a<-1 or hes140b< -1 or hes140d< -1 or hes140e < -1 or (hryear4=2015 and hes140c< -1 and not (hbnkprevly>1 and huse12pp=1)) then -1
	when hryear4>=2017 and (hes140c <= -2 or hes141 <= -2) then -1
  when hes150a=1 or hes150b=1 or hes150c=1 or hes150d=1 or hes150e=1 or hes150f=1 or hes150g=1 or hes150h=1 or hes150i=1 then 2
   else 1 end htyppaynonev2,


case when hryear4<2017 then null  when hryear4 >= 2019 then null   when hes140x < -1 or hes140x=2 or hes150x < -1 or hes150x=2 then -1  when huse12pp=99 or huse12cc=99 or huse12mo=99 or hes140a=3 or hes150a=3 or hes150a< -1 or hes150b< -1 or hes150c< -1 or hes150d< -1 or hes150e< -1 or hes150f< -1 or hes150g< -1 or hes150h< -1 or hes150i< -1
   or hes140a<-1 or hes140b< -1 or hes140d< -1 or hes140e < -1 or (hryear4=2015 and hes140c< -1 and not (hbnkprevly>1 and huse12pp=1)) then -1
	when hryear4>=2017 and (hes140c <= -2 or hes141 <= -2) then -1
   when htyppaybnkbp=1 or htyppaybnkchk=1 or htyppaybnkdc=1 or htyppaycc=1 or htyppaybnkmo=1 then 1
   else 2 end htyppaybnkav2,

case when hryear4<2017 then null  when hryear4 >= 2019 then null   when hes140x < -1 or hes140x=2 or hes150x < -1 or hes150x=2 then -1  when huse12pp=99 or huse12cc=99 or huse12mo=99 or hes140a=3 or hes150a=3 or hes150a< -1 or hes150b< -1 or hes150c< -1 or hes150d< -1 or hes150e< -1 or hes150f< -1 or hes150g< -1 or hes150h< -1 or hes150i< -1
   or hes140a<-1 or hes140b< -1 or hes140d< -1 or hes140e < -1 or (hryear4=2015 and hes140c< -1 and not (hbnkprevly>1 and huse12pp=1)) then -1
	when hryear4>=2017 and (hes140c <= -2 or hes141 <= -2) then -1
   when (htyppaybnkbp=1 or htyppaybnkchk=1 or htyppaybnkdc=1 or htyppaycc=1 or htyppaybnkmo=1) and htyppaycash=2 and htyppaypp=2 and htyppaynbnkmo=2 and htyppayoth=2 then 1
   else 2 end htyppaybnkov2,


case 
 when hryear4<2017 then null  when hryear4 >= 2019 then null  when hes140x < -1 or hes140x=2 or hes150x < -1 or hes150x=2 then -1 
when huse12pp=99 or huse12cc=99 or huse12mo=99 or hes140a=3 or hes150a=3 or hes150a< -1 or hes150b< -1 or hes150c< -1 or hes150d< -1 or hes150e< -1 or hes150f< -1 or hes150g< -1 or hes150h< -1 or hes150i< -1
   or hes140a<-1 or hes140b< -1 or hes140d< -1 or hes140e < -1 or (hryear4=2015 and hes140c< -1 and not (hbnkprevly>1 and huse12pp=1)) then -1 
	when hryear4>=2017 and (hes140c <= -2 or hes141 <= -2) then -1
when hunbnk=1 then -1

when  (not (hes140c = 1 or hes140d = 1 or hes140e = 1 or hes141 = 1) and   (htypincddbnk=1 or (htypincchkmo=1 and hunbnk=2 and htypinccc=2) ))
 and ((htyppaybnkbp=1 or htyppaybnkchk=1 or htyppaybnkdc=1 or htyppaycc=1 or htyppaybnkmo=1) and htyppaycash=2 and htyppaypp=2 and htyppaynbnkmo=2 and htyppayoth=2) then 1 else 2 end htypbnkov2,








case when hryear4<2015 then null
when hryear4 >= 2019 then null 
when huse12pp=99 or huse12cc=99 or huse12mo=99 or hes140a=3 or hes150a=3 or hes150a< -1 or hes150b< -1 or hes150c< -1 or hes150d< -1 or hes150e< -1 or hes150f< -1 or hes150g< -1 or hes150h< -1 or hes150i< -1
   or hes140a<-1 or hes140b< -1 or hes140d< -1 or hes140e < -1 or (hryear4=2015 and hes140c< -1 and not (hbnkprevly>1 and huse12pp=1)  )   or (hryear4>=2017 and (hes140c <= -2 or hes141 <= -2)) then 2 else 1 end hinutyp,

case when hryear4 >= 2021 then null when hryear4<2015 then null when hryear4>=2019 then 1 when hryear4<=2017 and (hes185<-1 or hes186<-1 or hes187<-1) then 2 else 1 end hinuphoneint,

case when hryear4<2017 then null 
when hryear4 >= 2019 then null 
when huse12pp=99 or huse12cc=99 or huse12mo=99 or hes140a=3 or hes150a=3 or hes150a< -1 or hes150b< -1 or hes150c< -1 or hes150d< -1 or hes150e< -1 or hes150f< -1 or hes150g< -1 or hes150h< -1 or hes150i< -1
   or hes140a<-1 or hes140b< -1 or hes140d< -1 or hes140e < -1 or  hes140c< -1   or hes140x < -1 or hes140x=2 or hes141 < -1 or hes150x < -1 or hes150x=2 then 2 else 1 end hinutypv2,




case  when hryear4<2017 then null  
when hryear4 >= 2019 then null

when hsav12= -1 or (hcred12ccorbnk=-1 or huse12afsc=99  or hcred12newapp=-1 or hcred12denied=-1 or hcred12discour=-1 or hbilldq=99  or hcred12cc=-1 or hcred12bnkv2=-1 or hcred12sc=-1 or hcred12car=-1 or hcred12hmln=-1 or hcred12sl=-1 or hcred12oth=-1) or 
(huse12pp=99 or huse12cc=99 or huse12mo=99 or hes140a=3 or hes150a=3 or hes150a< -1 or hes150b< -1 or hes150c< -1 or hes150d< -1 or hes150e< -1 or hes150f< -1 or hes150g< -1 or hes150h< -1 or hes150i< -1
   or hes140a<-1 or hes140b< -1 or hes140d< -1 or hes140e < -1 or  hes140c< -1   or hes140x < -1 or hes140x=2 or hes141 < -1 or hes150x < -1 or hes150x=2)  or hbankstatv3!=2 then -1 
when  hunbnk=1 then -1
when  hbankstatv3 = 2 and (not (hes140c = 1 or hes140d = 1 or hes140e = 1 or hes141 = 1) and   (htypincddbnk=1 or (htypincchkmo=1 and hunbnk=2 and htypinccc=2) ))
 and ((htyppaybnkbp=1 or htyppaybnkchk=1 or htyppaybnkdc=1 or htyppaycc=1 or htyppaybnkmo=1) and htyppaycash=2 and htyppaypp=2 and htyppaynbnkmo=2 and htyppayoth=2) and huse12afsc != 1 then 1
when  hbankstatv3 = 2 and (not (hes140c = 1 or hes140d = 1 or hes140e = 1 or hes141 = 1) and   (htypincddbnk=1 or (htypincchkmo=1 and hunbnk=2 and htypinccc=2) ))
 and ((htyppaybnkbp=1 or htyppaybnkchk=1 or htyppaybnkdc=1 or htyppaycc=1 or htyppaybnkmo=1) and htyppaycash=2 and htyppaypp=2 and htyppaynbnkmo=2 and htyppayoth=2) and huse12afsc = 1 then 2
when  hbankstatv3 = 2  and huse12afsc != 1 then 3
when  hbankstatv3 = 2 and huse12afsc = 1 then 4

else -1 end htypbnkoafsc,

case
when hryear4<2015 then null     
when hryear4>=2019 then 1
when hryear4=2015 and (hcred12ccorbnk=-1 or huse12afsc=99  or hcred12newapp=-1 or hcred12denied=-1 or hcred12discour=-1 or hbilldq=99  or hcred12cc=-1 or hcred12bnk=-1)  then 2
when hryear4=2017 and (hcred12ccorbnk=-1 or huse12afsc=99  or hcred12newapp=-1 or hcred12denied=-1 or hcred12discour=-1 or hbilldq=99  or hcred12cc=-1 or hcred12bnkv2=-1 or hcred12sc=-1 or hcred12car=-1 or hcred12hmln=-1 or hcred12sl=-1 or hcred12oth=-1)  then 2
else 1 end hinucred,

case
when hryear4<2015 then null     
when hryear4>=2019 then 1
when hryear4=2015 and (hcred12ccorbnk=-1 or huse12afsc=99 or hcred12newapp=-1 or hcred12denied=-1 or hcred12discour=-1 or hbilldq=99 or hcred12cc=-1 or hcred12bnk=-1 or huse12pdl=99 or huse12pwn=99 or huse12atl=99 or huse12rto=99 or huse12ral=99)  then 2
when hryear4=2017 and (hcred12ccorbnk=-1 or huse12afsc=99 or hcred12newapp=-1 or hcred12denied=-1 or hcred12discour=-1 or hbilldq=99 or hcred12cc=-1 or hcred12bnkv2=-1 or hcred12sc=-1 or hcred12car=-1 or hcred12hmln=-1 or hcred12sl=-1 or hcred12oth=-1 or huse12pdl=99 or huse12pwn=99 or huse12atl=99 or huse12rto=99 or huse12ral=99) then 2
else 1 end hinunbcred,

case when hryear4<2017 then null 
when hryear4 >= 2019 then null 
	when hsav12= -1 or (hcred12ccorbnk=-1 or huse12afsc=99  or hcred12newapp=-1 or hcred12denied=-1 or hcred12discour=-1 or hbilldq=99  or hcred12cc=-1 or hcred12bnkv2=-1 or hcred12sc=-1 or hcred12car=-1 or hcred12hmln=-1 or hcred12sl=-1 or hcred12oth=-1) or 
(huse12pp=99 or huse12cc=99 or huse12mo=99 or hes140a=3 or hes150a=3 or hes150a< -1 or hes150b< -1 or hes150c< -1 or hes150d< -1 or hes150e< -1 or hes150f< -1 or hes150g< -1 or hes150h< -1 or hes150i< -1
   or hes140a<-1 or hes140b< -1 or hes140d< -1 or hes140e < -1 or  hes140c< -1   or hes140x < -1 or hes140x=2 or hes141 < -1 or hes150x < -1 or hes150x=2) then 2
else 1 end hinuec,


case
when hryear4<2015 then null
when hryear4 >= 2021 then null 
when hryear4=2015 and (hcred12ccorbnk=-1 or huse12afsc=99  or hcred12newapp=-1 or hcred12denied=-1 or hcred12discour=-1 or hbilldq=99  or hcred12cc=-1 or hcred12bnk=-1) then -1
when hryear4=2017 and (hcred12ccorbnk=-1 or huse12afsc=99  or hcred12newapp=-1 or hcred12denied=-1 or hcred12discour=-1 or hbilldq=99  or hcred12cc=-1 or hcred12bnkv2=-1 or hcred12sc=-1 or hcred12car=-1 or hcred12hmln=-1 or hcred12sl=-1 or hcred12oth=-1) then -1
when hcred12newapp=1 or hcred12discour=1 or huse12afsc=1 then 1 else 2
end hcred12int,

case
when hryear4<2015 then null
when hryear4 >= 2021 then null 
when hryear4=2015 and (hcred12ccorbnk=-1 or huse12afsc=99  or hcred12newapp=-1 or hcred12denied=-1 or hcred12discour=-1 or hbilldq=99  or hcred12cc=-1 or hcred12bnk=-1) then -1 
when hryear4=2017 and (hcred12ccorbnk=-1 or huse12afsc=99  or hcred12newapp=-1 or hcred12denied=-1 or hcred12discour=-1 or hbilldq=99  or hcred12cc=-1 or hcred12bnkv2=-1 or hcred12sc=-1 or hcred12car=-1 or hcred12hmln=-1 or hcred12sl=-1 or hcred12oth=-1)  then -1
when hcred12denied=1 or hcred12discour=1 or huse12afsc=1 then 1 else 2
end hcred12undem,

case when hbnkprev = 99 then -1 else hbnkprev end hbnkprevv2,
case when hbnkprevly= 99 then -1 else hbnkprevly end hbnkprevlyv2,
case when hbnkprevly= 99 then -1 when hbnkprevly = 98 then -1 else hbnkprevly end hbnkprevlyv3,

case when hryear4 >= 2019 then null when hbnkfutr= 99 then -1 else hbnkfutr end hbnkfutrv2,

case 
	when hryear4<2017 then null
	when hryear4 >= 2019 then null 
	when hsav12= -1 or (hcred12ccorbnk=-1 or huse12afsc=99  or hcred12newapp=-1 or hcred12denied=-1 or hcred12discour=-1 or hbilldq=99  or hcred12cc=-1 or hcred12bnkv2=-1 or hcred12sc=-1 or hcred12car=-1 or hcred12hmln=-1 or hcred12sl=-1 or hcred12oth=-1) or 
( huse12pp=99 or huse12cc=99 or huse12mo=99 or hes140a=3 or hes150a=3 or hes150a< -1 or hes150b< -1 or hes150c< -1 or hes150d< -1 or hes150e< -1 or hes150f< -1 or hes150g< -1 or hes150h< -1 or hes150i< -1
   or hes140a<-1 or hes140b< -1 or hes140d< -1 or hes140e < -1 or  hes140c< -1   or hes140x < -1 or hes140x=2 or hes141 < -1 or hes150x < -1 or hes150x=2)  or hbankstatv3!=2 then -1

 when (htyppaybnkbp=1 or htyppaybnkchk=1 or htyppaybnkdc=1 or htyppaycc=1 or htyppaybnkmo=1) and htyppaycash=2 and htyppaypp=2 and htyppaynbnkmo=2 and htyppayoth=2  and 
(htypincddbnk=1 or (htypincchkmo=1 and hunbnk=2 and htypinccc=2))  and not (hes140c = 1 or hes140d = 1 or hes140e = 1 or hes141 = 1)  then 1 else 2
end 

htypbnkound,

case when hryear4<2015 then null when hryear4 >= 2017 then null  when hfinfobnk = 99 or hfinedu = 99 or hfinedbnk = 99 then 2 else 1 end hinulearn,

hagele15,hagele16,hagele17,hagege16,hagele18,hagege18,unbnk_yn,ptypchk_yn,ptypsav_yn,ptypunk_yn,
 hagege15_17,hagege15_18,pnum15_17chk,pnum15_17sav,

 pnumlt15bnk, pnumlt15unbnk, pnumlt15unk, pnum15_17bnk, pnum15_17unbnk, pnum15_17unk,
 pnum_mill_bnk,pnum_mill_unbnk,pnum_mill_unk,
 pnumge18bnk, pnumge18unbnk, pnumge18unk,




pnum,
p_hrs_wrk,
p_hrs_wrk2,
p_weekly_earn,
pnum_mill,
 hlivwfam,
 hlivwnonfam,

 hlivwfam_mill,
 hlivwnonfam_mill,

case when hryear4 >=2015 then null else gtmetsta  end gtmetsta5yr03,

case when gtmetsta = 2 and msa5yr13 > 0  then 1 else gtmetsta  end gtmetsta5yr13,

case when hryear4 <= 2017 then null else heub50 end hbnkint,

case when hryear4 >= 2021 then null when hryear4 <= 2017 then null else heub55a1 end hunbnkr1v4,
case when hryear4 >= 2021 then null when hryear4 <= 2017 then null else heub55a2 end hunbnkr2v4,
case when hryear4 >= 2021 then null when hryear4 <= 2017 then null else heub55b1 end hunbnkr3v4,
case when hryear4 >= 2021 then null when hryear4 <= 2017 then null else heub55b2 end hunbnkr4v4,
case when hryear4 >= 2021 then null when hryear4 <= 2017 then null else heub55c end hunbnkr5v4,
case when hryear4 >= 2021 then null when hryear4 <= 2017 then null else heub55d end hunbnkr6v4,
case when hryear4 >= 2021 then null when hryear4 <= 2017 then null else heub55e end hunbnkr7v4,
case when hryear4 >= 2021 then null when hryear4 <= 2017 then null else heub55f end hunbnkr8v4,
case when hryear4 >= 2021 then null when hryear4 <= 2017 then null else heub55g end hunbnkr9v4,
case when hryear4 >= 2021 then null when hryear4 <= 2017 then null else heub55h end hunbnkr10v4,

case when hryear4 >= 2021 then null when hryear4 <= 2017 then null when (heub55a1 = 2 and heub55a2 = 2 and heub55b1 = 2 and heub55b2 = 2 and heub55c = 2 and heub55d = 2 and heub55e = 2 and heub55f = 2 and heub55g = 2 and heub55h = 2) then 1 when (heub55a1 = 1 or heub55a2 = 1 or heub55b1 = 1 or heub55b2 = 1 or heub55c = 1 or heub55d = 1 or heub55e = 1 or heub55f = 1 or heub55g = 1 or heub55h = 1) then 2 else -1 end hunbnkrnonev4,

case when hryear4 >= 2021 then null when hryear4 <= 2017 then null when (heub55a1 = 2 and heub55a2 = 2 and heub55b1 = 2 and heub55b2 = 2 and heub55c = 2 and heub55d = 2 and heub55e = 2 and heub55f = 2 and heub55g = 2 and heub55h = 2) then 98 else heub60 end hunbnkrmv4,

case when hryear4 <= 2017 then null else hepw10a end hppwhere1v2,
case when hryear4 <= 2017 then null else hepw10b end hppwhere2v2,
case when hryear4 <= 2017 then null else hepw10c end hppwhere3v2,
case when hryear4 <= 2017 then null else hepw10d end hppwhere4v2,
case when hryear4 <= 2017 then null else hepbuse end hppbankstill,
case when hryear4 >= 2021 then null when hryear4 <= 2017 then null when (henbmo10=1 or henbcc10=1 or henbbp10=1) then 1 else 2 end huse12moccbp,
case when hryear4 >= 2021 then null when hryear4 <= 2017 then null when heb20 = 2 then -1 when hea20 = -2 then 98 else hea20 end hbnksatisbnk,
case when hryear4 >= 2021 then null when hryear4 <= 2017 then null when heb20 = 2 then -1 when hea20 = -2 then 98 when (hea20=1 or hea20=2) then 1 when (hea20=3 or hea20=4) then 2 else hea20 end hbnksatisbnkv2,

case when hryear4 >= 2021 then null when hryear4 <= 2017 then null when (heb20 = 1 or heub10 = 2) then -1 when (heb20 = 2 and hepbuse = 1) then -1 when hea20 = -2 then 98 else hea20 end hbnksatisunbnk,
case when hryear4 >= 2021 then null when hryear4 <= 2017 then null when (heb20 = 1 or heub10 = 2) then -1 when (heb20 = 2 and hepbuse = 1) then -1 when hea20 = -2 then 98  when (hea20=1 or hea20=2) then 1 when (hea20=3 or hea20=4) then 2 else hea20 end hbnksatisunbnkv2,

case when hryear4 >= 2021 then null when hryear4 <= 2017 then null when heb20 = 2 then -1 when hea40 = -2 then 98 else hea40 end hbnkfeebnk,
case when hryear4 >= 2021 then null when hryear4 <= 2017 then null when heb20 = 2 then -1 when hea40 = -2 then 98 when (hea40 =1 or hea40 =2) then 1 when (hea40 =3 or hea40 =4) then 2 else hea40 end hbnkfeebnkv2,
case when hryear4 >= 2021 then null when hryear4 <= 2017 then null when heb20 = 1 then -1 when (heb20 = 2 and hepbuse = 1) then -1 when hea40 = -2 then 98 else hea40 end hbnkfeeunbnk,
case when hryear4 >= 2021 then null when hryear4 <= 2017 then null when heb20 = 1 then -1 when (heb20 = 2 and hepbuse = 1) then -1 when hea40 = -2 then 98 when (hea40 =1 or hea40 =2) then 1 when (hea40 =3 or hea40 =4) then 2 else hea40 end hbnkfeeunbnkv2,

case when hryear4 <= 2017 then null else henbp2p end huse12p2p,
case when hryear4 <= 2017 then null else henbbp10 end huse12bp,

case when hryear4 >= 2021 then null when hryear4 <= 2017 then null when henbmo10 = 2 then 4 else henbmo15 end hfreqmo,
case when hryear4 >= 2021 then null when hryear4 <= 2017 then null when henbcc10 = 2 then 4 else henbcc15 end hfreqcc,
case when hryear4 <= 2017 then null when henbrm10 = 2 then 4 else henbrm15 end hfreqrm,
case when hryear4 <= 2017 then null when henbbp10 = 2 then 4 else henbbp15 end hfreqbp,

case when hryear4 >= 2021 then null when hryear4 <= 2017 then null when (henbmo10 = 1 or henbcc10 = 1 or henbrm10 = 1 or henbp2p = 1 or henbbp10 = 1) then 1 else 2 end huse12nbtrans,
case when hryear4 >= 2021 then null when hryear4 <= 2017 then null when (henbmo15 = 1 and henbmo16 = 1) then 1 when (henbmo15 = 2 and henbmo16 = 1) then 2 when (henbmo15 = 1 and henbmo16 = 2) then 3 when (henbmo15 = 2 and henbmo16 = 2) then 4 when henbmo15 = 3 then 5 else 6 end hfreqmobill,

case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10a end hbnkaccm1v2,
case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10b end hbnkaccm2v2,
case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10c end hbnkaccm3v2,
case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10e end hbnkaccm4v2,
case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10d end hbnkaccm5v2,
case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10f end hbnkaccm6v2,
case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then 1 else 2 end hbnkaccm7v2,
case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 when (heba10a = 1) and (heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then 1 when (heba10a = 1) and (heba10b = 1 or heba10c = 1 or heba10d = 1 or heba10e = 1 or heba10f = 1) then 2 when (heba10a = 2) and (heba10b = 1 or heba10c = 1 or heba10d = 1 or heba10e = 1 or heba10f = 1) then 3 end hbranchstatv2,
case 
when hryear4<=2017 then null
when hunbnk=1 then -1
when 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10a end=1 then 1 else 0 end+ 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10b end=1 then 1 else 0 end+ 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10c end=1 then 1 else 0 end+ 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10d end=1 then 1 else 0 end+ 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10e end=1 then 1 else 0 end+ 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10f end=1 then 1 else 0 end
=0 then 0

when 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10a end=1 then 1 else 0 end+ 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10b end=1 then 1 else 0 end+ 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10c end=1 then 1 else 0 end+ 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10d end=1 then 1 else 0 end+ 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10e end=1 then 1 else 0 end+ 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10f end=1 then 1 else 0 end
=1 then 1
when 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10a end=1 then 1 else 0 end+ 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10b end=1 then 1 else 0 end+ 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10c end=1 then 1 else 0 end+ 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10d end=1 then 1 else 0 end+ 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10e end=1 then 1 else 0 end+ 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10f end=1 then 1 else 0 end
>1 then 2
else 99 end hbnkaccmnbrv2,
case 

when hryear4<=2017 then null 
when hunbnk=1 then null
else
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10a end=1 then 1 else 0 end+ 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10b end=1 then 1 else 0 end+ 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10c end=1 then 1 else 0 end+ 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10d end=1 then 1 else 0 end+ 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10e end=1 then 1 else 0 end+ 
case when case when hryear4 <= 2017 then null when heb20 = 2 then -1 when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1 else heba10f end=1 then 1 else 0 end

end
hnumbmths_cv2,


case when (hryear4 < 2017 or hryear4 = 2019 or hryear4 = 2021) then null
when (hryear4 = 2017) and (hes1600a = 1 or hes1600f = 1) then 1
when (hryear4 = 2017) and (hes1600a = 2 and hes1600f = 2) then 2
when (hryear4 >= 2023) and (heccc10 = 1 or hecpl10 = 1) then 1
when (hryear4 >= 2023) and (heccc10 = 2 and hecpl10 = 2) then 2
end hcred12ccorbnkv2


from foo a
')
# from hh3 a , hh0 b, hh1 c, hh2 d , hhp e
# where a.qstnum=b.qstnum and a.perrp=b.perrp 
# and a.qstnum=c.qstnum and a.perrp=c.perrp and a.qstnum=d.qstnum and a.perrp=d.perrp and a.qstnum=e.qstnum and a.perrp=e.perrp



hh5=sqldf('select a.qstnum,a.perrp,
case when hryear4 <= 2015 then null when hryear4 >= 2023 then null when (hryear4 = 2017 and hes2 = 2 and hes70 = 1) then 1 when (hryear4 = 2017 and hes2 = 2 and hes70 = 2) then 2 when (hryear4 = 2019 and heb20 = 2 and (heba10a = 1 or hebr10 = 1)) then 1 when (hryear4 = 2019 and heb20 = 2 and hebr10 = 2) then 2 when hryear4 = 2021 then heub70 else -1 end hbnkbrgounb,
case when hryear4 <= 2019 then null else heub55a2 end hunbnkr1v5,
case when hryear4 <= 2019 then null else heub55b1 end hunbnkr2v5,
case when hryear4 <= 2019 then null else heub55b2 end hunbnkr3v5,
case when hryear4 <= 2019 then null else heub55c end hunbnkr4v5,
case when hryear4 <= 2019 then null else heub55d end hunbnkr5v5,
case when hryear4 <= 2019 then null else heub55e end hunbnkr6v5,
case when hryear4 <= 2019 then null else heub55f end hunbnkr7v5,
case when hryear4 <= 2019 then null else heub55g1 end hunbnkr8v5,
case when hryear4 <= 2019 then null else heub55g2 end hunbnkr9v5,
case when hryear4 <= 2019 then null else heub55h end hunbnkr10v5,
case when hryear4 <= 2019 then null when (heub55a2 = 2 and heub55b1 = 2 and heub55b2 = 2 and heub55c = 2 and heub55d = 2 and heub55e = 2 and heub55f = 2 and heub55g1 = 2 and heub55g2 = 2 and heub55h = 2) then 1 when (heub55a2 = 1 or heub55b1 = 1 or heub55b2 = 1 or heub55c = 1 or heub55d = 1 or heub55e = 1 or heub55f = 1 or heub55g1 = 1 or heub55g2 = 1 or heub55h = 1) then 2 else -1 end hunbnkrnonev5,
case when hryear4 <= 2019 then null when (heub55a2 = 2 and heub55b1 = 2 and heub55b2 = 2 and heub55c = 2 and heub55d = 2 and heub55e = 2 and heub55f = 2 and heub55g1 = 2 and heub55g2 = 2 and heub55h = 2) then 98 else heub60 end hunbnkrmv5,
case when hryear4 <= 2019 then null else hepsuse10 end husenowops,
case when hryear4 <= 2019 then null else hepuse10 end husenowpp,
case when hryear4 <= 2019 then null else hebuse20a end huse12bnkrsna,
case when hryear4 <= 2019 then null else hebuse20b end huse12bnkrsnb,
case when hryear4 <= 2019 then null else hebuse20c end huse12bnkrsnc,
case when hryear4 <= 2019 then null else hebuse20d end huse12bnkrsnd,
case when hryear4 <= 2019 then null else hebuse20e end huse12bnkrsne,
case when hryear4 <= 2019 then null else hebuse20f end huse12bnkrsnf,
case when hryear4 <= 2019 then null else hebuse20g end huse12bnkrsng,
case when hryear4 >= 2023 then null when hryear4 <= 2019 then null when (hebuse20a = 2 and hebuse20b = 2 and hebuse20c = 2 and hebuse20d = 2 and hebuse20e = 2 and hebuse20f = 2 and hebuse20g = 2) then 1 when (hebuse20a = 1 or hebuse20b = 1 or hebuse20c = 1 or hebuse20d = 1 or hebuse20e = 1 or hebuse20f = 1 or hebuse20g = 1) then 2 else -1 end huse12bnkrsnnone,

case when hryear4 <= 2019 then null else hepsus20a end huse12opsrsna,
case when hryear4 <= 2019 then null when hryear4 > 2021 then null else hepsus20b end huse12opsrsnb,
case when hryear4 <= 2019 then null else hepsus20c end huse12opsrsnc,
case when hryear4 <= 2019 then null else hepsus20d end huse12opsrsnd,
case when hryear4 <= 2019 then null else hepsus20e end huse12opsrsne,
case when hryear4 <= 2019 then null else hepsus20f end huse12opsrsnf,
case when hryear4 <= 2019 then null else hepsus20g end huse12opsrsng,

case when hryear4 <= 2019 then null  when hryear4 > 2021 then null  when (hepsus20a = 2 and hepsus20b = 2 and hepsus20c = 2 and hepsus20d = 2 and hepsus20e = 2 and hepsus20f = 2 and hepsus20g = 2) then 1 when (hepsus20a = 1 or hepsus20b = 1 or hepsus20c = 1 or hepsus20d = 1 or hepsus20e = 1 or hepsus20f = 1 or hepsus20g = 1) then 2 else -1 end huse12opsrsnnone,

case when hryear4 <= 2019 then null else hepuse20a end huse12pprsna,

case when hryear4 <= 2019 then null when hryear4 >2021 then null else hepuse20b end huse12pprsnb,

case when hryear4 <= 2019 then null else hepuse20c end huse12pprsnc,
case when hryear4 <= 2019 then null else hepuse20d end huse12pprsnd,
case when hryear4 <= 2019 then null else hepuse20e end huse12pprsne,
case when hryear4 <= 2019 then null else hepuse20f end huse12pprsnf,
case when hryear4 <= 2019 then null else hepuse20g end huse12pprsng,

case when hryear4 <= 2019 then null when hryear4 >2021 then null when (hepuse20a = 2 and hepuse20b = 2 and hepuse20c = 2 and hepuse20d = 2 and hepuse20e = 2 and hepuse20f = 2 and hepuse20g = 2) then 1 when (hepuse20a = 1 or hepuse20b = 1 or hepuse20c = 1 or hepuse20d = 1 or hepuse20e = 1 or hepuse20f = 1 or hepuse20g = 1) then 2 else -1 end huse12pprsnnone,

case when hryear4 <= 2019 then null else hepsus301 end hopslink1,
case when hryear4 <= 2019 then null else hepsus302 end hopslink2,
case when hryear4 <= 2019 then null else hepsus303 end hopslink3,
case when hryear4 <= 2019 then null else hepsus304 end hopslink4,
case when hryear4 <= 2019 then null else hepsus305 end hopslink5,

case when hryear4 <= 2019 then null when hryear4 > 2021 then null else henbmo201 end huse12morsn1,

case when hryear4 <= 2019 then null else henbmo202 end huse12morsn2,
case when hryear4 <= 2019 then null else henbmo203 end huse12morsn3,
case when hryear4 <= 2019 then null else henbmo204 end huse12morsn4,
case when hryear4 <= 2019 then null else henbmt10 end huse12mt,

case when hryear4 <= 2019 then null when hryear4 > 2021 then null else henbmt201 end huse12mtrsn1,

case when hryear4 <= 2019 then null else henbmt202 end huse12mtrsn2,
case when hryear4 <= 2019 then null else henbmt203 end huse12mtrsn3,
case when hryear4 <= 2019 then null else henbmt204 end huse12mtrsn4,
case when hryear4 <= 2019 then null else henbcc20 end huse12ccfrom,
case when hryear4 <= 2019 then null else hecpl20 end hcred12bnkamt,

case when hryear4 >= 2023 then null when hryear4 <= 2019 then null else hecnbpl10 end hcred12nbnk,
case when hryear4 <= 2019 then null else hecnbpl20 end hcred12nbnkamt,
case when hryear4 <= 2019 then null else hele10 end hbnknewv2,
case when hryear4 <= 2019 then null else hele20a end hevent1v2,
case when hryear4 <= 2019 then null else hele20b end hevent2v2,
case when hryear4 <= 2019 then null else hele20c end hevent3v2,
case when hryear4 <= 2019 then null else hele20d end hevent4v2,
case when hryear4 <= 2019 then null else hele20e end hevent5v2,


case when hryear4 >= 2023 then null when hryear4 <= 2019 then null when heub15 != 1 then -1 when hele301 = 1 then 1 else 2 end hevent1bcv2,
case when hryear4 >= 2023 then null when hryear4 <= 2019 then null when heub15 != 1 then -1 when hele302 = 1 then 1 else 2 end hevent3bcv2,
case when hryear4 >= 2023 then null when hryear4 <= 2019 then null when hele10 != 1 then -1 when hele401 = 1 then 1 else 2 end hevent2bov2,
case when hryear4 >= 2023 then null when hryear4 <= 2019 then null when hele10 != 1 then -1 when hele402 = 1 then 1 else 2 end hevent4bov2,
case when hryear4 >= 2023 then null when hryear4 <= 2019 then null when hele10 != 1 then -1 when hele403 = 1 then 1 else 2 end hevent5bov2,


case
when hryear4 <= 2017 then null
when heb20 = 2 then -1
when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1
when (heba10a = 1 or heba10b = 1) and (heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then 1
when (heba10a = 1 or heba10b = 1) and (heba10c = 1 or heba10d = 1 or heba10e = 1 or heba10f = 1) then 2
when (heba10a = 2 and heba10b = 2) and (heba10c = 1 or heba10d = 1 or heba10e = 1 or heba10f = 1) then 3
end hbranchatmstatv2,
case
when hryear4 < 2013 or hryear4 >= 2019 then null
when hes2 = 2 then -1
when hes2g7 = 1 or hes2g1 <= -1 then -1
when (hes2g1 = 1 or hes2g2 = 1) and (hes2g3 = 2 and hes2g4 = 2 and hes2g5 = 2 and hes2g6 = 2) then 1
when (hes2g1 = 1 or hes2g2 = 1) and (hes2g3 = 1 or hes2g4 = 1 or hes2g5 = 1 or hes2g6 = 1) then 2
when (hes2g1 = 2 and hes2g2 = 2) and (hes2g3 = 1 or hes2g4 = 1 or hes2g5 = 1 or hes2g6 = 1) then 3
end hbranchatmstat,

case when hryear4 >= 2023 then null 
when hryear4 <= 2019 then null
when heb20 = 2 then -1
when hebuse20b = 1 or hebuse20c = 1 then 1
when hebuse20b = 2 and hebuse20c = 2 then 2
end huse12bnkrsnbc,

case when hryear4 <= 2019 then null
when hryear4 >2021 then null

when hepsuse10 = 2 then -1
when hepsus20b = 1 or hepsus20c = 1 then 1
when hepsus20b = 2 and hepsus20c = 2 then 2
end huse12opsrsnbc,


case when hryear4 <= 2019 then null
when hryear4 > 2021 then null 
when hepuse10 = 2 then -1
when hepuse20b = 1 or hepuse20c = 1 then 1
when hepuse20b = 2 and hepuse20c = 2 then 2
end huse12pprsnbc,

case 
when hryear4 >= 2023 then null 
when hryear4 <= 2019 then null
when heub10 = 2 or heub15 = 2 then 1
when heub15 = 1 then 2
when hele10 = 1 then 3
when hele10 = 2 then 4
end hbnktransv3,

case when hrhtype = 1 or hrhtype = 2 then 1
when hrhtype = 4 and (hagege18 = 1 and hagele17 >= 1) then 2
when hrhtype = 4 and (hagege18 != 1 or hagele17 = 0) then 3
when hrhtype = 3 and (hagege18 = 1 and hagele17 >= 1) then 4
when hrhtype = 3 and (hagege18 != 1 or hagele17 = 0) then 5
when hrhtype = 7 then 6
when hrhtype = 6 then 7
else 8 end hhtypev2,

case 
when hryear4>=2023 then null
when hryear4 < 2021 then null
when heb20 = 2 then 1
when heb20 = 1 and (henbcc10 = 1 or henbmo10 = 1 or henbmt203 = 1 or hecnbpdl = 1 or hecnbpwn = 1 or hecnbtax = 1 or hecnbatl = 1 or hecnbrto = 1) then 2
else 3
end hbankstatv5,

case 
when hryear4 >= 2023 then null
when hryear4 < 2021 then null 
when heb20 = 2 then null
else
case when hebuse20a=1 then 1 else 0 end+ 
case when hebuse20b=1 then 1 else 0 end+ 
case when hebuse20c=1 then 1 else 0 end+ 
case when hebuse20d=1 then 1 else 0 end+ 
case when hebuse20e=1 then 1 else 0 end+ 
case when hebuse20f=1 then 1 else 0 end
end huse12bnkrsnnum_c,


case when hryear4 < 2021 then null 
when hryear4 > 2021 then null 

when hepsuse10 = 2 then null
else
case when hepsus20a=1 then 1 else 0 end+ 
case when hepsus20b=1 then 1 else 0 end+ 
case when hepsus20c=1 then 1 else 0 end+ 
case when hepsus20d=1 then 1 else 0 end+ 
case when hepsus20e=1 then 1 else 0 end+ 
case when hepsus20f=1 then 1 else 0 end
end huse12opsrsnnum_c,

case when hryear4 < 2021 then null 
when hryear4 > 2021 then null 

when hepuse10 = 2 then null
else
case when hepuse20a=1 then 1 else 0 end+ 
case when hepuse20b=1 then 1 else 0 end+ 
case when hepuse20c=1 then 1 else 0 end+ 
case when hepuse20d=1 then 1 else 0 end+ 
case when hepuse20e=1 then 1 else 0 end+ 
case when hepuse20f=1 then 1 else 0 end
end huse12pprsnnum_c,

case
when hryear4 < 2021 then null
when henbmt203 = 1 then 1
else 2
end huse12rmv2,

case
when hryear4 > 2021 then null

when hryear4 < 2021 then null
when henbmt201 = 1 then 1
else 2
end huse12bpv2,

case
when hryear4>=2023 then null
when hryear4 < 2021 then null
when heb20 = 2 then 1
when heb20 = 1 and (henbcc10 = 1 or henbmo10 = 1 or henbmt203 = 1) and (hecnbpdl = 2 and hecnbpwn = 2 and hecnbtax = 2 and hecnbatl = 2 and hecnbrto = 2) then 2
when heb20 = 1 and (henbcc10 = 2 and henbmo10 = 2 and (henbmt10 = 2 or henbmt203 = 2)) and (hecnbpdl = 1 or hecnbpwn = 1 or hecnbtax = 1 or hecnbatl = 1 or hecnbrto = 1) then 3
when heb20 = 1 and (henbcc10 = 1 or henbmo10 = 1 or henbmt203 = 1) and (hecnbpdl = 1 or hecnbpwn = 1 or hecnbtax = 1 or hecnbatl = 1 or hecnbrto = 1) then 4
else 5
end hbankstattype,

case when hryear4 < 2021 then null 
when hryear4 > 2021 then null 
when henbmo10 = 2 then null
else
case when henbmo201=1 then 1 else 0 end+ 
case when henbmo202=1 then 1 else 0 end+ 
case when henbmo203=1 then 1 else 0 end
end huse12morsnnum_c,

case when hryear4 < 2021 then null 
when hryear4 > 2021 then null 

when henbmt10 = 2 then null
else
case when henbmt201=1 then 1 else 0 end+ 
case when henbmt202=1 then 1 else 0 end+ 
case when henbmt203=1 then 1 else 0 end
end huse12mtrsnnum_c,

case 
when hryear4 >= 2023 then null 
when hryear4 < 2021 then null 
when (hebuse20b=1 or hebuse20c=1 or hepsus20b=1 or hepsus20c=1 or hepuse20b=1 or hepuse20c=1 or henbmo201=1 or henbmt201=1 or henbcc20=1) then 1
else 2
end hbillincomemethod,

case 
when hryear4 >= 2023 then null 
when hryear4 < 2021 then null 
when (hebuse20e=1 or hebuse20f=1 or hepsus20e=1 or hepsus20f=1 or hepuse20e=1 or hepuse20f=1 or henbmo203=1) then 1
else 2
end hpurchasemethod,


case 
when hryear4 >= 2023 then null 
when hryear4 < 2021 then null 
when (hebuse20d=1 or hepsus20d=1 or hepuse20d=1 or henbmo202=1 or henbmt202=1 or henbmt203=1) then 1
else 2
end hsendmoneymethod,

case 
when hryear4 >= 2023 then null 
when hryear4 < 2021 then null 
when (hebuse20a=1 or hepsus20a=1 or hepuse20a=1) then 1
else 2
end hsavemethod,

case 
when (hryear4 < 2013 and hryear4 = 2021) then null
when (hryear4 = 2019 or hryear4 >= 2023) and heh30 = 1 then 1
when (hryear4 = 2019 or hryear4 >= 2023) and heh30 != 1 then 2
when (hryear4 >= 2015 and hryear4 <= 2017) and hes186 = 1 then 1
when (hryear4 >= 2015 and hryear4 <= 2017) and hes186 != 1 then 2
when (hryear4 = 2013) and hes48 = 1 then 1
when (hryear4 = 2013) and hes48 != 1 then 2
end hsmphonev2

from
foo a
')
# hh3 a , hh0 b, hh1 c, hh2 d , hhp e
# where a.qstnum=b.qstnum and a.perrp=b.perrp 
# and a.qstnum=c.qstnum and a.perrp=c.perrp and a.qstnum=d.qstnum and a.perrp=d.perrp and a.qstnum=e.qstnum and a.perrp=e.perrp



hh6=sqldf('select a.qstnum,a.perrp,
case when hryear4 <= 2021 then null else hebnpl10 end hcred12bnpl,
case when hryear4 <= 2021 then null else hebnpl20 end hcred12bnplfreq,
case when hryear4 <= 2021 then null else hebnpl301 end hcred12bnplonl,
case when hryear4 <= 2021 then null else hebnpl302 end hcred12bnplper,
case when hryear4 <= 2021 then null else hebnpl40 end hcred12bnpldq,
case when hryear4 <= 2021 then null else hecryp10 end huse12cryp,
case when hryear4 <= 2021 then null else hecryp201 end huse12cryprsn1,
case when hryear4 <= 2021 then null else hecryp202 end huse12cryprsn2,
case when hryear4 <= 2021 then null else hecryp203 end huse12cryprsn3,
case when hryear4 <= 2021 then null else hecryp204 end huse12cryprsn4,
case when hryear4 <= 2021 then null else hecryp205 end huse12cryprsn5,
case
when (hryear4 <= 2019) then null
when (hepuse10 = 1 and hepsuse10 = 2) then 1
when (hepuse10 = 2 and hepsuse10 = 1) then 2
when (hepuse10 = 1 and hepsuse10 = 1) then 3
when (hepuse10 = 2 and hepsuse10 = 2) then 4
end husenowppops,

case when hryear4 <= 2021 then null 
when hepsuse10 = 2 then null
else
case when hepsus20a=1 then 1 else 0 end+ 
case when hepsus20b=1 then 1 else 0 end+ 
case when hepsus20c=1 then 1 else 0 end+ 
case when hepsus20d=1 then 1 else 0 end+ 
case when hepsus20e=1 then 1 else 0 end+ 
case when hepsus20f=1 then 1 else 0 end+
case when hepsus20g=1 then 1 else 0 end
end huse12opsrsnnum_cv2,

case when hryear4 <= 2021 then null 
when hepuse10 = 2 then null
else
case when hepuse20a=1 then 1 else 0 end+ 
case when hepuse20b=1 then 1 else 0 end+ 
case when hepuse20c=1 then 1 else 0 end+ 
case when hepuse20d=1 then 1 else 0 end+ 
case when hepuse20e=1 then 1 else 0 end+ 
case when hepuse20f=1 then 1 else 0 end+
case when hepuse20g=1 then 1 else 0 end
end huse12pprsnnum_cv2,
case when hryear4 <= 2021 then null 
when henbmo10 = 2 then null
else
case when henbmo201=1 then 1 else 0 end+ 
case when henbmo202=1 then 1 else 0 end+ 
case when henbmo203=1 then 1 else 0 end+
case when henbmo204=1 then 1 else 0 end
end huse12morsnnum_cv2,
case when hryear4 <= 2021 then null 
when henbmt10 = 2 then null
else
case when henbmt201=1 then 1 else 0 end+ 
case when henbmt202=1 then 1 else 0 end+ 
case when henbmt203=1 then 1 else 0 end+
case when henbmt204=1 then 1 else 0 end
end huse12mtrsnnum_cv2,
case
when hryear4 <= 2021 then null
when (hecnbpdl = 1 or hecnbpwn = 1 or hecnbtax = 1 or hecnbatl = 1 or hecnbrto = 1) then 1
when (hecnbpdl = 2 and hecnbpwn = 2 and hecnbtax = 2 and hecnbatl = 2 and hecnbrto = 2) then 2
end huse12AFSCv3,
case when hryear4 <= 2021 then null else hecnbtax end huse12ralv2,
case
when hryear4 <= 2021 then null
when heb20 = 2 then 1
when heb20 = 1 and (henbcc10 = 1 or henbmo10 = 1 or henbmt203 = 1 or hecnbpdl = 1 or hecnbpwn = 1 or hecnbtax = 1 or hecnbatl = 1 or hecnbrto = 1) then 2
else 3
end hbankstatv6,
case
when hryear4 <= 2017 then null
when heb20 = 2 then -1
when (heba10a = 2 and heba10b = 2 and heba10c = 2 and heba10d = 2 and heba10e = 2 and heba10f = 2) then -1
when (heba10c = 1 or heba10d = 1 or heba10e = 1) and (heba10a = 2 and heba10b = 2 and heba10f = 2) then 1
when (heba10c = 1 or heba10d = 1 or heba10e = 1) and (heba10a = 1 or heba10b = 1 or heba10f = 1) then 2
when (heba10c = 2 and heba10d = 2 and heba10e = 2) and (heba10a = 1 or heba10b = 1 or heba10f = 1) then 3
end hmobonltelstatv2,
case
when hryear4 < 2013 or hryear4 >= 2019 then null
when hes2 = 2 then -1
when hes2g7 = 1 then -1
when (hes2g3 = 1 or hes2g4 = 1 or hes2g5 = 1) and (hes2g1 = 2 and hes2g2 = 2 and hes2g6 = 2) then 1
when (hes2g3 = 1 or hes2g4 = 1 or hes2g5 = 1) and (hes2g1 = 1 or hes2g2 = 1 or hes2g6 = 1) then 2
when (hes2g3 = 2 and hes2g4 = 2 and hes2g5 = 2) and (hes2g1 = 1 or hes2g2 = 1 or hes2g6 = 1) then 3
end hmobonltelstat,
case when (hrhtype = 1 or hrhtype = 2) and (hagele17 >= 1) then 1
when (hrhtype = 1 or hrhtype = 2) and (hagele17 = 0) then 2
when (hrhtype = 4 or hrhtype = 3) and (hagege18 = 1 and hagele17 >= 1) then 3
when (hrhtype = 4 or hrhtype = 3) and (hagege18 != 1 or hagele17 = 0) then 4
when hrhtype = 7 then 5
when hrhtype = 6 then 6
else 7 end hhtypev3,
case
when (hryear4 <= 2019) then null
when (heb20 = 2 and hepuse10 = 2 and hepsuse10 = 2) then 1
else 2
end hunbnkcashonly,

case when hryear4 <= 2021 then null else hepsus20b end huse12opsrsnbv2,

case when hryear4 <= 2021 then null when (hepsus20a = 2 and hepsus20b = 2 and hepsus20c = 2 and hepsus20d = 2 and hepsus20e = 2 and hepsus20f = 2 and hepsus20g = 2) then 1 when (hepsus20a = 1 or hepsus20b = 1 or hepsus20c = 1 or hepsus20d = 1 or hepsus20e = 1 or hepsus20f = 1 or hepsus20g = 1) then 2 else -1 end huse12opsrsnnonev2,

case when hryear4 <= 2021 then null else hepuse20b end huse12pprsnbv2,

case when hryear4 <= 2021 then null when (hepuse20a = 2 and hepuse20b = 2 and hepuse20c = 2 and hepuse20d = 2 and hepuse20e = 2 and hepuse20f = 2 and hepuse20g = 2) then 1 when (hepuse20a = 1 or hepuse20b = 1 or hepuse20c = 1 or hepuse20d = 1 or hepuse20e = 1 or hepuse20f = 1 or hepuse20g = 1) then 2 else -1 end huse12pprsnnonev2,

case when hryear4 <= 2021 then null else henbmo201 end huse12morsn1v2,

case when hryear4 <= 2021 then null else henbmt201 end huse12mtrsn1v2



from
foo a
')

print(nrow(hh0))
print(nrow(hh1))
print(nrow(hh2))
print(nrow(hh3))
print(nrow(hh4))
print(nrow(hh5))
print(nrow(hh6))


library(plyr)
hh=join(hh0,hh1)
hh=join(hh,hh2)
hh=join(hh,hh3)
hh=join(hh,hh4)
hh=join(hh,hh5)
hh=join(hh,hh6)
hh=join(hh,ppv)

if (exists("imp"))
{
print('fffff')
hh=unique(join(hh,imp_flags))

}


print(nrow(hh))
# suppress certain variables not used
# removed hbaseint
hh<-subset(hh,select=-c(pbaseresp,psupresp,hansppq,hanslstq,psupwgtk,punbnk,pbnktyp))
gc()
return (hh);
}
