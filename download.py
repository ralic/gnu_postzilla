#!/usr/bin/python

###################################################################################
#                          postzilla.py  -  description
#                             -------------------
#    begin                : Apr  3, 2005
#    last update          : Jul 14, 2007
#    copyright            : (C) 2005, 2006, 2007 by Carlos Castillo and Luis Useche
#    email                : {carlos.d.castillo|useche}@gmail.com
#
###################################################################################
#     This file is part of Postzilla.
#
#     Postzilla is free software; you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation; either version 2 of the License, or
#     (at your option) any later version.
#
#     Foobar is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with Foobar; if not, write to the Free Software
#     Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
###################################################################################

import string, base64

from httplib import HTTPConnection
from ftplib  import FTP
from urlparse import urlparse
import time

import common

class DownloadPart:
    """
    Abstract class that represents a thread which download a part of the file
    
    Methods:
    - download:     method which must be executed to this thread
    """
    def __init__(self):
        if self.__class__ is DownloadPart:
            raise NotImplementedError

    def download(self):
        raise NotImplementedError


class HttpDownloadPart(DownloadPart):
    """
    Thread which download a part of the file
    
    Attributes:
    - url:          the url introduced by the user
    - firstbyte:    byte of the file where this part begin
    - lastbyte:     byte of the file where this part finalize
    - order:        number of the part (begin with 0)
    - progressbar:  progress bar for the user. Is needed here to be updated
    - toDownload:   Bytes to be downloaded for this part
    - sizeToRead:   Number of bytes to be readed in every iteration

    Methods:
    - download:     It open and close the file of this part and the to the
                    server. It manages errors.
    - write_bytes:  read the conection to the server and write the bytes
                    on the file. Update the progress bar.
    - get_request:  create a request and return it
    """

    def __init__(self, url, firstbyte, lastbyte, order, progressbar, user, password, filename):
        self.url = urlparse(url)
        self.firstbyte = firstbyte
        self.lastbyte = lastbyte
        self.toDownload = lastbyte-firstbyte+1
        self.order = order
        self.sizeToRead = (lastbyte-firstbyte+1)/100
        self.progressbar = progressbar
        self.user = user
        self.password = password
        self.filename = filename
        self.stop = False
        
    def download(self):
        f = open(self.filename,'wb')
        f.seek(self.firstbyte)

        conn = HTTPConnection(self.url[1])
        conn.request('GET',self.url[2],headers=self.get_headers())
        response = conn.getresponse()

        #verifying that response is ok
        common.verify_http_response(response)

        self.write_bytes(response,f)
        
        conn.close()
        f.close()

    def write_bytes(self,hte,f):
        while (self.toDownload):
            toRead = min(self.sizeToRead,self.toDownload)
            buf = hte.read(toRead)

            f.write(buf)
            self.firstbyte += len(buf)
            self.toDownload -= len(buf)

            # if the thread must stop, we finish
            if(self.stop): return
            
            #update the progressbar
            self.progressbar.update(self.order, len(buf))
            
    def get_headers(self):
        extra_headers = {'User-agent':'Mozilla/5.0', 'Range': 'bytes=%d-%d'%(self.firstbyte, self.lastbyte)}

        #if i got user and password i login
        if self.user and self.password:
            enc_pass = 'Basic %s'%string.strip(base64.encodestring(self.user + ':' + self.password))
            extra_headers['Authorization'] = enc_pass

        return extra_headers

    def get_file_size(self,url,user,password):
        parsedURL = urlparse(url)
        conn = HTTPConnection(parsedURL[1])
        
        #authentication
        extra_headers = {}
        if user and password:
            enc_pass = 'Basic %s'%string.strip(base64.encodestring(user + ':' + password))
            extra_headers = {'Authorization': enc_pass}
        
        conn.request('GET',parsedURL[2],headers=extra_headers)
        r = conn.getresponse()

        #verify that the request go well
        common.verify_http_response(r)

        length = r.length
        
        conn.close()

        return length
    
    get_file_size = classmethod(get_file_size)

    def must_stop(self):
        self.stop = True

class FtpDownloadPart(DownloadPart):
    def __init__(self, url, firstbyte, lastbyte, order, progressbar, user, password,filename):
        self.url = urlparse(url)
        self.firstbyte = firstbyte
        self.lastbyte = lastbyte
        self.order = order
        self.toDownload = lastbyte-firstbyte+1
        self.sizeToRead = (lastbyte-firstbyte+1)/100
        self.progressbar = progressbar
        self.user = user
        self.password = password
        self.filename = filename
        self.stop = False

    def download(self):
        f = open(self.filename,'wb')
        f.seek(self.firstbyte)

        ftp = FTP(self.url[1])
        
        #if i got user and password i login in
        if self.user and self.password:
            response = ftp.login(self.user,self.password)
        else:
            response = ftp.login()
            
        #verifying that the login is ok
        common.verify_ftp_response(response)
        
        #begin from the firstbyte
        ftp.sendcmd("SYST")
        ftp.sendcmd("TYPE I")
        ftp.sendcmd("PASV")
        
        sock = ftp.transfercmd(("RETR %s"%(self.url[2])),self.firstbyte)

        self.write_bytes(sock,f)
        
        sock.close()

    def write_bytes(self,sock,f):

        while self.toDownload:

            toRead = min(self.sizeToRead,self.toDownload)
            buf = sock.recv(toRead)

            f.write(buf)
            
            self.firstbyte += len(buf)
            self.toDownload -= len(buf)
        
            # if the thread must stop, we finish
            if(self.stop): return
            
            self.progressbar.update(self.order, len(buf))

    def get_file_size(self,url,user,password):
        parsedURL = urlparse(url)
        print "Connecting to %s..."%(parsedURL[1])
        ftp = FTP(parsedURL[1])
        
        print "Login..."
        #authentication stuff
        if user and password:
            response = ftp.login(user,password)
        else:
            response = ftp.login()
            
        #verify that the login was right
        common.verify_ftp_response(response)
        
        length = ftp.size(parsedURL[2])
        
        ftp.quit()
        
        return length
    
    get_file_size = classmethod(get_file_size)

    def must_stop(self):
        self.stop = True
