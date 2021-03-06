import xml.etree.ElementTree as ET
import numpy as np
import structure
from multiprocessing import Process,Pool
PRECIS=6

class elph_structure():
 def __init__(self,ph_structure,lambda_or_elph):
  self.ALL_COLORS=[[] for i in range(len(ph_structure.Q))] 
  self.KPOINTS_all_all_q=[]
  self.lambda_or_elph=lambda_or_elph
 def parallel_job(self,structure,el_structure,ph_structure):
  nq=len(ph_structure.Q)
  no_of_pool=nq
  with Pool(no_of_pool) as pol:
   results=pol.map(self.single_job,
              [[int(q+1),structure,ph_structure,el_structure,self.lambda_or_elph] for q in range(nq)])
   self.ALL_COLORS=[ i[0] for i in results]
   self.KPOINTS_all_all_q=[ i[1] for i in results]
 def single_job(self,args):
  [q,structure,ph_structure,el_structure,lambda_or_elph]=args
  print('calculations for '+str(q)+'. of total '+str(len(ph_structure.Q))+' q points')
  elph_q=elph_structure_single_q(ph_structure)
  elph_q.make_kpoints_single_q(q,structure,ph_structure.Q[q-1])
  elph_q.read_elph_single_q(q,ph_structure,el_structure,structure )
  elph_q.elph_single_q_in_whole_kgrid(q,structure,\
                ph_structure,el_structure,lambda_or_elph)  #'lambda' or 'elph'
  return [elph_q.COLORS,elph_q.KPOINTS_all]
  print(str(q)+'. point ended')
  
 def sum_over_q(self,ph_structure,structure,el_structure):
  print('summing over q...')
  SUMMED_COLORS=[[0 for k in range(len(self.KPOINTS_all_all_q[0]))] for jband in self.ALL_COLORS[0]]
  for band in range(len(SUMMED_COLORS)):
   for numq,col_q in enumerate(self.ALL_COLORS):
    for numk,k in enumerate(self.KPOINTS_all_all_q[numq]):
     SUMMED_COLORS[band][numk]+=col_q[band][k[3]]*ph_structure.multiplicity_of_qs[numq]
  if self.lambda_or_elph=='elph':
   h=open('elph.frmsf','w')
  else:
   h=open('lambda.frmsf','w')
  h.write(str(structure.no_of_kpoints[0])+' '+str(structure.no_of_kpoints[1])+' ' +str(structure.no_of_kpoints[2])+'\n')
  h.write('1\n'+str(len(el_structure.bands_num))+'\n')
  for i in structure.e:
   for j in i:
    h.write(str(j)+' ')
   h.write('\n')
  for bnd in el_structure.ENE_fs:
   for k in structure.allk:
    h.write(str(bnd[k[3]])+'\n')
  for bnd in SUMMED_COLORS:
   for k in bnd:
    h.write(str(k)+'\n')
  h.close()

 

class elph_structure_single_q():
 def __init__(self,ph_structure):
  self.ELPH_sum=[]
  self.q=1
  self.elph_dir=ph_structure.elph_dir
  self.prefix=ph_structure.prefix
  self.KPOINTS=[] #[0:2] list of noneq k at given q [3] its no in list of nonequivalent kpoints at given q  (self.KPOINTS)  and [4] its no in list of nonequivalent kpoints of electronic structure (el_structure.NONEQ)
  self.WEIGHTS_OF_K=[]
  self.nbnd_el=0
  self.fermi_nbnd_el=0
  self.nkp=0
  self.KPOINTS_all=[] #[0:2] list of allk [3] its no in list of nonequivalent kpoints at given q  (self.KPOINTS)  
  self.KPQ=[] #[0] k+q, [1] its no in list of nonequivalent kpoints at given q  (self.KPOINTS)  
  self.lambda_or_elph='' #'lambda' or 'elph'
  self.COLORS=[]

 def make_kpoints_single_q(self,q_no,basic_structure,q):
  print('make kgrid at given q')
  self.pm=[0,-1,1]
  tree = ET.parse(self.elph_dir+'elph.'+str(q_no)+'.1.xml')
  root = tree.getroot()
  self.nkp=int(root.find('PARTIAL_EL_PHON/NUMBER_OF_K').text)
  self.KPOINTS=[ [ round(float(m),PRECIS)\
         for m in root.find(
          'PARTIAL_EL_PHON/K_POINT.'+str(k)+'/COORDINATES_XK'
          ).text.split() ]\
           for k in range(1,self.nkp+1)]
  for numki,ki in enumerate(self.KPOINTS): 
   self.KPOINTS[numki].append(numki)
   found=0
   for h1 in self.pm:
    for k1 in self.pm:
     for l1 in self.pm:
      ki2=[round(kk,PRECIS) for kk in 
                 (ki[0:3]-(h1*basic_structure.e[0]+k1*basic_structure.e[1]+l1*basic_structure.e[2]))]
      for j in basic_structure.allk:
       if ki2[0]==j[0] and ki2[1]==j[1] and ki2[2]==j[2]:
        self.KPOINTS[numki].append(j[3])
        found=1
        break
      if found==1: break
     if found==1: break
    if found==1: break
  structure_new=structure.structure()
  structure_new.NONEQ=self.KPOINTS
  structure_new.SYMM=basic_structure.SYMM
  structure_new.e=basic_structure.e
  structure_new.no_of_kpoints=basic_structure.no_of_kpoints
 # structure_new.check_symm()
  structure_new.make_kgrid()
  self.KPOINTS_all=structure_new.allk
  self.WEIGHTS_OF_K=structure_new.WK
#  self.KPOINTS_all_all_q.append(structure_new.allk)
  self.KPQ=[]
  for k in self.KPOINTS:
   self.KPQ.append(structure_new.find_k_plus_q(k, self.KPOINTS_all,q))


 def w0gauss(self,x):
  degauss=0.002
  x2=x/degauss
  sqrtpm1= 1. / 1.77245385090551602729
  # cold smearing  (Marzari-Vanderbilt-DeVita-Payne)
  arg = min (200., (x2 - 1.0 /  (2.0)**0.5 ) **2.)
  return sqrtpm1 * np.exp ( - arg) * (2.0 - ( 2.0)**0.5 * x2)/degauss

 
 def read_elph_single_q(self,q_point_no,ph_structure,el_structure,structure): 
  print(str(q_point_no)+': read elph from file...')
  #read info from first file
  tree = ET.parse(self.elph_dir+'elph.'+str(q_point_no)+'.1.xml')
  root = tree.getroot()
  self.nbnd_el=int(root.find('PARTIAL_EL_PHON/NUMBER_OF_BANDS').text)
  #choose only bands which cross EF and sum over j in pairs <i,j>
  print(str(q_point_no)+': From all '+str(self.nbnd_el)+' bands detected in elph calc. only bands ',el_structure.bands_num,' cross EF and will be written in frmsf')
  self.fermi_nbnd_el=len(el_structure.bands_num)
#  ELPH=[[[ [] for k in range(self.nkp)] for j in range(self.nbnd_el)] for i in range(self.fermi_nbnd_el)] #stores elph[k][ibnd][jbnd][nmode]
  ELPH=np.zeros(shape=(self.nbnd_el,self.fermi_nbnd_el,\
                self.nkp,ph_structure.no_of_modes), dtype=complex) #stores elph[k][ibnd][jbnd][nmode]
#  self.ELPH_sum1=np.zeros(shape=(self.fermi_nbnd_el,\
#           self.nkp,ph_structure.no_of_modes,ph_structure.no_of_modes),dtype=complex)
  self.ELPH_sum=np.zeros(shape=(self.fermi_nbnd_el,\
           self.nkp,ph_structure.no_of_modes),dtype=complex)
#stores elph[ibnd][k][nmode][mmode]

  #read elph  from all files
  for mode in range(1,len(ph_structure.NONDEG[q_point_no-1])+1):
   #elph
   tree = ET.parse(self.elph_dir+'elph.'+str(q_point_no)+'.'+str(mode)+'.xml')
   root = tree.getroot()
   for country in root.iter('PARTIAL_EL_PHON'):
    for k in range(1,self.nkp+1):
     for town in country.iter('K_POINT.'+str(k)):
      partial_elph=town.find('PARTIAL_ELPH')
      if k==1: 
       npert0=int(partial_elph.get('size'))/self.nbnd_el/self.nbnd_el
       npert=int(npert0)
       if npert/npert0!=1: 
        print(str(q_point_no)+"WARNING: npert is not int, but is equal to"+str(npert0))
      elph_k=[ complex(float(m.replace(',',' ').split()[0]), 
                       float(m.replace(',',' ').split()[1])) 
                for m in partial_elph.text.split('\n') if len(m.split())>0  ]
      for jband in range(self.nbnd_el):
       for numiband,iband in enumerate(el_structure.bands_num):
        for iipert in range(npert):
         ELPH[jband][numiband][k-1][iipert]=\
          elph_k[iipert*self.nbnd_el*npert+jband*self.nbnd_el+iband]
#          elph_k[iipert*self.nbnd_el*npert+iband*self.nbnd_el+jband] --rather wrong
#          elph_k[jband*self.nbnd_el*npert+iband*npert+iipert] --wrong
     
  '''
  #sum over jband
  for iband in range(self.fermi_nbnd_el):
    for k in range(1,self.nkp+1):
      for iipert in range(ph_structure.no_of_modes):
       w2ii=ph_structure.FREQ[q_point_no-1][iipert]
       for jjpert in range(ph_structure.no_of_modes):
        w2jj=ph_structure.FREQ[q_point_no-1][jjpert]
        if w2ii<=0 or w2jj<=0:
          self.ELPH_sum1[iband][k-1][iipert][jjpert]=0.
        else:
         for jband in range(self.nbnd_el):
           gep2 = np.conjugate(ELPH[jband][iband][k-1][iipert])\
		  *ELPH[jband][iband][k-1][jjpert]\
                  /w2ii**0.5/w2jj**0.5
           self.ELPH_sum1[iband][k-1][iipert][jjpert]+=\
             self.w0gauss(el_structure.ef-el_structure.ENE[jband][self.KPOINTS[self.KPQ[k-1][1]][4]])\
             *gep2\
             *self.WEIGHTS_OF_K[self.KPQ[k-1][1]]
  for iband in range(self.fermi_nbnd_el):
   for k in range(1,self.nkp+1):
#    phi=scompact_dyn(ph_structure.nat,self.ELPH_sum[iband][k-1])
    phi= self.dyn_pattern_to_cart(ph_structure.nat, ph_structure.PATT[q_point_no-1],  self.ELPH_sum1[iband][k-1])
    phi=self.trntnsc(ph_structure.nat,phi, structure.at, structure.e, -1)
    phi=self.trntnsc(ph_structure.nat,phi, structure.at, structure.e, 1)
    phi=self.compact_dyn(ph_structure.nat, phi)
    self.ELPH_sum[iband][k-1]=self.sum_over_jjpert\
                     (ph_structure.nat,ph_structure.DYN[q_point_no-1],phi)
  '''
  #sum over jband
  for iband in range(self.fermi_nbnd_el):
    for k in range(1,self.nkp+1):
      sum_weight=0
      for iipert in range(ph_structure.no_of_modes):
       w2ii=ph_structure.FREQ[q_point_no-1][iipert]
       for jjpert in range(ph_structure.no_of_modes):
        w2jj=ph_structure.FREQ[q_point_no-1][jjpert]
        if w2ii>=0.0001 or w2jj>=0.0001:
         for jband in range(self.nbnd_el):
           weight=self.w0gauss(el_structure.ef-el_structure.ENE[jband][self.KPOINTS[self.KPQ[k-1][1]][4]])*self.WEIGHTS_OF_K[self.KPQ[k-1][1]]
           gep2 = np.conjugate(ELPH[jband][iband][k-1][iipert])\
		  *ELPH[jband][iband][k-1][jjpert]\
                  /(w2ii**0.5)/(w2jj**0.5)
           self.ELPH_sum[iband][k-1]+=weight*gep2
           sum_weight+=weight
      if sum_weight!=0: self.ELPH_sum[iband][k-1]=self.ELPH_sum[iband][k-1]/sum_weight



  '''
  #sum over jband
  #GORZEJ
  for iband in range(self.fermi_nbnd_el):
    for k in range(1,self.nkp+1):
      for iipert in range(ph_structure.no_of_modes):
       w2ii=ph_structure.FREQ[q_point_no-1][iipert]
       if w2ii<=0:
          self.ELPH_sum[iband][k-1][iipert]=0.
       else:
         for jband in range(self.nbnd_el):
           gep2 = np.conjugate(ELPH[jband][iband][k-1][iipert])*ELPH[jband][iband][k-1][iipert]/w2ii
           self.ELPH_sum[iband][k-1]+=\
             self.w0gauss(el_structure.ef-el_structure.ENE[jband][self.KPOINTS[self.KPQ[k-1][1]][4]])\
             *gep2\
             *self.WEIGHTS_OF_K[self.KPQ[k-1][1]]
  '''


 def elph_single_q_in_whole_kgrid(self,q,structure,ph_structure,el_structure,l_or_gep):
  print(str(q)+': print elph to file')
  self.lambda_or_elph=l_or_gep
  self.COLORS=np.zeros(shape=(len(el_structure.bands_num), len(self.KPOINTS)))
  if self.lambda_or_elph=='elph':
   for numk,k in enumerate(self.KPOINTS):
    for jband in range(len(el_structure.bands_num)): 
     self.COLORS[jband][numk]= np.abs(np.sum(self.ELPH_sum[jband][numk]))  
  else:
   for numk,k in enumerate(self.KPOINTS):
    for jband in range(len(el_structure.bands_num)): 
     self.COLORS[jband][numk]= 2.*np.abs(np.sum([elph/ph_structure.FREQ[q-1][num] for num,elph in enumerate(self.ELPH_sum[jband][numk])]))  #abs=sqrt(real^2+im^2)

  
  print (q,":",len(self.COLORS),[len(i) for i in self.COLORS])
  print (q,":",len(el_structure.ENE_fs),[len(i) for i in el_structure.ENE_fs])
  print (q,":",len(structure.allk))
  if self.lambda_or_elph=='elph':
   h=open('elph'+str(q)+'.frmsf','w')
  else:
   h=open('lambda'+str(q)+'.frmsf','w')
  h.write(str(structure.no_of_kpoints[0])+' '+str(structure.no_of_kpoints[1])+' ' +str(structure.no_of_kpoints[2])+'\n')
  h.write('1\n'+str(len(el_structure.bands_num))+'\n')
  for i in structure.e:
   for j in i:
    h.write(str(j)+' ')
   h.write('\n')
  for bnd in el_structure.ENE_fs:
   for k in structure.allk:
    h.write(str(bnd[k[3]])+'\n')
  for bnd in self.COLORS:
   for k in self.KPOINTS_all:
    h.write(str(bnd[k[3]])+'\n')
  h.close()
#  self.ALL_COLORS[q-1]=COLORS







 def elph_matrix_to_gep(self,nat,dyn,gep2): #,w2,pat):
#  gep=[[ [[complex(0,0) for ii in range(3*nat)] for ik in range(self.nkp)] for ib in range(self.nbnd_el)] for jb in range(self.nbnd_el)]
#  gep2=[[ [[[complex(0,0) for jj in range(3*nat)] for ii in range(3*nat)] for ik in range(self.nkp)] for ib in range(self.nbnd_el)] for jb in range(self.nbnd_el)]
  gep=np.zeros(shape=(self.fermi_nbnd_el,self.nkp,3*nat),dtype=complex)
#  gep2=np.zeros(shape=(self.nbnd_el,self.fermi_nbnd_el,self.nkp,3*nat,3*nat),dtype=complex)

  '''DOES NOT CHANGE RESULTS
  for ik in range(self.nkp):
     for ib in range(self.nbnd_el):
      for jb in range(self.fermi_nbnd_el):
        for ii in range(3*nat):
          gep[jb][ib][ik][ii] = np.dot(pat[ii], el_ph_mat[jb][ib][ik])
        gep[jb][ib][ik] = np.matmul(gep[jb][ib][ik], dyn)
  '''
 
  for ik in range(self.nkp):
#     for jb in range(self.nbnd_el):
      for ib in range(self.fermi_nbnd_el):
#        for ii in range(3*nat):
#         for jj in range(3*nat):
#          gep2[jb][ib][ik][ii][jj] = np.conjugate(el_ph_mat[jb][ib][ik][ii])*el_ph_mat[jb][ib][ik][jj]
        for nu in range(3*nat):
         for mu in range(3*nat):
          for vu in range(3*nat):
           gep[ib][ik][nu] += np.conjugate(dyn[mu][nu])*(gep2[ib][ik][mu][vu]*dyn[vu][nu])

  return gep

###########STAFF FROM ELPHON################
 def dyn_pattern_to_cart(self,nat, patt,dyn):
  phi=np.zeros(shape=(nat,nat,3,3), dtype=complex)
  for i in range(3*nat):
   na=i/3
   icart=i-3*na
   for j in range(3*nat):
    nb=j/3
    jcart=j-3*nb
    work=0+0j
    for mu in range(3*nat):
     for nu in range(3*nat):
      work += patt[i][mu]*dyn[mu][nu]*np.conjugate(patt[j][nu])
    phi[na][nb][icart][jcart]=work
  return phi

 def trntnsc(self,nat,phi,at,bg,iflg):
#     ! forward transformation (crystal to cartesian axis)
  if iflg>0:
   for na in range(nat):
    for nb in range(nat):
     wrk=phi[na][nb][:]
     phi=np.zeros(shape=(nat,nat,3,3), dtype=complex)
     for i in range(3):
      for j in range(3):
       for k in range(3):
        for l in range(3):
         phi[na][nb][i][j]+= wrk[k][l]*bg[i][k]*bg[j][l]
#     ! backward transformation (cartesian to crystal axis)
  else:
   for na in range(nat):
    for nb in range(nat):
     wrk=np.zeros(shape=(nat,nat,3,3), dtype=complex)
     for i in range(3):
      for j in range(3):
       for k in range(3):
        for l in range(3):
         wrk[na][nb][i][j]+= phi[na][nb][k][l]*at[k][i]*at[l][j]
     phi[na][nb]=wrk[:]
  return phi

 def compact_dyn(self,nat,phi):
#Dynamical matrix from a 3,3,nat,nat format to a 3xnat, 3xnat format
  dyn=np.zeros(shape=(3*nat,3*nat), dtype=complex)
  for na in range(nat):
   for icart in range(3):
    imode=3*na+icart
    for nb in range(nat):
     for jcart in range(3):
      jmode=3*nb+jcart
      dyn[imode][jmode]=phi[na][nb][icart][jcart]
  return dyn

 def scompact_dyn(self,nat,dyn):
#Dynamical matrix from a 3xnat, 3xnat to a 3,3,nat,nat format 
  phi=np.zeros(shape=(nat,nat,3,3), dtype=complex)
  for na in range(nat):
   for icart in range(3):
    imode=3*na+icart
    for nb in range(nat):
     for jcart in range(3):
      jmode=3*nb+jcart
      phi[na][nb][icart][jcart]=dyn[imode][jmode]
  return phi

 def sum_over_jjpert(self,nat,dyn,elph):
  gamma_over_freq_nu=np.zeros(shape=(3*nat), dtype=complex)
  for nu in range(3*nat):
   for mu in range(3*nat):
    for vu in range(3*nat):
              gamma_over_freq_nu[nu] += \
                np.conjugate(dyn[mu][nu]) *elph[mu][vu] *dyn[vu][nu]
   gamma_over_freq_nu[nu] = np.pi * gamma_over_freq_nu[nu] / 2.
  return gamma_over_freq_nu
############################

