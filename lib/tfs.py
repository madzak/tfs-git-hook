#
# Copyright (c) Matt Hawley, http://hgtfshook.codeplex.com
#
# This software may be used and distributed under the
# Microsoft Public License (Ms-PL).
#

from ntlm import HTTPNtlmAuthHandler
from xml.sax.saxutils import escape
import xml.etree.ElementTree as et
from datetime import datetime
import re, httplib, uuid, urllib2, urlparse, subprocess, sys

EMAIL_RE = re.compile("^(.*) <(.*)>$")

# Adapted From:
# Copyright (c) Matt Hawley, http://hgtfshook.codeplex.com
#
# This software may be used and distributed under the
# Microsoft Public License (Ms-PL).
#
class SoapService:
    NS_SOAP_ENV = "{http://schemas.xmlsoap.org/soap/envelope/}"
    NS_XSI = "{http://www.w3.org/2001/XMLSchema-instance}"
    NS_XSD = "{http://www.w3.org/2001/XMLSchema}"

    def __init__(self, url, username, password):        
        scheme, netloc, path, params, query, fragment = urlparse.urlparse(url)
        self.host = netloc
        self.url = '%s://%s%s/WorkItemTracking/v1.0/ClientService.asmx' % (scheme, netloc, path)        
        self.username = username
        self.password = password

    def _appendElement(self, name, value, parent):
        element = et.SubElement(parent, name)
        element.text = value

    def _appendNullElement(self, name, parent):
        element = et.Element(name, {SoapService.NS_XSI + 'nil': 'true'})
        parent.append(element)

    def _buildHeader(self, envelope):
        header = self._getHeader()
        if header is None:
            return
        envHeader = et.SubElement(envelope, SoapService.NS_SOAP_ENV + 'Header')
        envHeader.append(header)

    def _buildMessage(self, bodyMessage):
        envelope = et.Element(SoapService.NS_SOAP_ENV + 'Envelope')
        self._buildHeader(envelope)
        body = et.SubElement(envelope, SoapService.NS_SOAP_ENV + 'Body')
        body.append(bodyMessage)
        return envelope

    def _send(self, action, body):
        passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
        passman.add_password(None, self.url, self.username, self.password)
        proxy = urllib2.ProxyHandler({})
        ntlm = HTTPNtlmAuthHandler.HTTPNtlmAuthHandler(passman)

        opener = urllib2.build_opener(proxy, ntlm)
        urllib2.install_opener(opener)

        message = self._buildMessage(body)
        xmlMessage = et.tostring(message)

        headers = {'Host':self.host,
                   'Content-Type':'text/xml; charset=utf-8',
                   'Content-Length':len(xmlMessage),
                   'SOAPAction':action}

        request = urllib2.Request(self.url, xmlMessage, headers)
        response = urllib2.urlopen(request)
        output = response.read()
        if response.fp.status == 200:
            return et.XML(output)

        raise urllib2.HTTPError(response.geturl(), response.fp.status, response.fp.reason, None, response.fp)

    def _getHeader(self):
        return None

class TfsClientService(SoapService):
    WIT_URL = "http://schemas.microsoft.com/TeamFoundation/2005/06/WorkItemTracking/ClientServices/03"
    NS_WIT = '{%s}' % WIT_URL
    _default_computedColumns = {'System.RevisedDate':None, 'System.ChangedDate':None, 'System.PersonId':None}

    def __init__(self, url, username, password, columns, computedColumns):
        SoapService.__init__(self, url, username, password)

        self.columns = {}
        if columns:
            self.columns.update(columns)
        
        self.computedColumns = TfsClientService._default_computedColumns
        if computedColumns:
            self.computedColumns.update(computedColumns)

    def _buildComputedColumns(self, parent):
        cols = et.SubElement(parent, 'ComputedColumns')
        for name, value in self.computedColumns.iteritems():
            et.SubElement(cols, 'ComputedColumn', {'Column':name})

    def _buildColumns(self, parent):
        cols = et.SubElement(parent, 'Columns')
        for name, value in self.columns.iteritems():
            col = et.SubElement(cols, 'Column', {'Column':name})
            et.SubElement(col, 'Value').text = value

    def _buildElement(self, method):
        return et.Element(method, {'xmlns': TfsClientService.WIT_URL})

    def _getAction(self, method):
        return '"%s/%s"' % (TfsClientService.WIT_URL, method)        

    def _getHeader(self):
        requestHeader = self._buildElement('RequestHeader')
        self._appendElement('Id', 'uuid:%s' % uuid.uuid4(), requestHeader)
        return requestHeader

    def _getColumns(self, table):
        columnData = {}
        columns = table.findall(str.format('./{0}columns//{0}c', TfsClientService.NS_WIT))
        values = table.findall(str.format('./{0}rows/{0}r//{0}f', TfsClientService.NS_WIT))

        if len(values) == 0:
            return None

        i = 0
        for field in values:
            fieldIndex = field.get('k', None)
            if fieldIndex:
                for j in range(i, int(fieldIndex)):
                    key = columns[j].find('./%sn' % TfsClientService.NS_WIT).text
                    columnData[key] = None
                index = int(fieldIndex)
            else:
                key = columns[i].find('./%sn' % TfsClientService.NS_WIT).text
                columnData[key] = field.text
            i += 1
            
        return columnData

    def getWorkItem(self, id):
        method = 'GetWorkItem'
        body = self._buildElement(method)
        self._appendElement('workItemId', str(id), body)
        self._appendElement('revisionId', '0', body)
        self._appendElement('minimumRevisionId', '0', body)
        self._appendNullElement('asOfDate', body)
        self._appendElement('useMaster', "true", body)
        response = self._send(self._getAction(method), body)

        tables = response.findall(str.format('./{0}Body/{1}GetWorkItemResponse/{1}workItem//{1}table', SoapService.NS_SOAP_ENV, TfsClientService.NS_WIT))
        for t in tables:
            if t.get('name') == 'WorkItemInfo':
                return self._getColumns(t)
        return None

    def addWorkItemComment(self, id, rev, comment):
        method = 'Update'
        body = self._buildElement(method)
        package = et.SubElement(body, 'package')
        subPackage = et.SubElement(package, 'Package', {'xmlns':''})
        update = et.SubElement(subPackage, 'UpdateWorkItem', {'ObjectType':'WorkItem', 'WorkItemID':str(id), 'Revision':str(rev)})
        et.SubElement(update, 'InsertText', {'FieldName':'System.History', 'FieldDisplayName':'History'}).text = comment
        self._buildComputedColumns(update)
        self._buildColumns(update)

        self._send(self._getAction(method), body)
