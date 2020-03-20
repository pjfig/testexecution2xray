#!/usr/bin/env python
"""
    Module that import Robot Framework test execution to XRAY.



    To compile this script we used pyinstaller (https://www.pyinstaller.org/)

    Install it with Python's pip:

        pip install pyinstaller


    Make sure that you have installed every dependencies of the script, such as lxml, requests,etc.

    Go to location path of rfw2xray_results.py and make sure that constants.py are also on that path.

    Compile with the following command:

        pyinstaller --onefile rfw2xray_results.py

    Upon executing this command a folder named 'dist/' will be created.
    The generated executable is located in that folder. It can generate executable for windows or linux.

"""
import argparse
from argparse import RawTextHelpFormatter
from urlparse import urljoin
import requests
import json
import os
import lxml.etree as ET
import re
import base64
import time
import sys
from datetime import datetime

import rfw2xray_auth
import testexec_builder as teb

import constants
#####################HEADER#######################
__author__ = "Paulo Figueira"
__copyright__ = "Copyright 2018, Altran Portugal"
__credits__ = ["Paulo Figueira", "Bruno Calado", "Rui Pinto"]

__licence__ = ""
__version__ = "1.0"
__maintainer__ = "Paulo Figueira"
__email__ = "paulo.figueira@altran.com"
__status__ = "Development"

#####################################################


# special Keywords
evidence_KWs = ['Capture Page Screenshot']
log_KWs = ['Log']

def _log_step(step, kw_xml, kw_name):
    """
    Check if is a log keyword, if true adds a comment to the respective test step

    :param current_step: Current test step to save log
    :param kw_xml: Current keyword XML element
    :param kw_name: Current keyword name
    :return:
        Boolean value, True if current keyword is a log Keyword, False otherwise
    """
    if kw_name in log_KWs:  # in case step is a LOGGING step
        log_args_text = [log_args.text for log_args in kw_xml.findall(constants.XPATH_LOG_ARGS)]
        if len(log_args_text) >= 2:
            log_text, log_level, _ = log_args_text
            if log_level == constants.WARN or log_level == constants.ERROR:

                # add log to step comment
                #step.add_to_comment('{}:{}\n'.format(log_level, log_text))
                
                comment = teb.path_get(step,constants.STEP_COMMENT)
                
                comment = comment + '{}:{}\n'.format(log_level, log_text)
                teb.path_set(step, constants.STEP_COMMENT, teb.path_get(step,constants.STEP_COMMENT) + 
                                                        '{}:{}\n'.format(log_level, log_text))
        
        return True
    else:
        return False


def _evidence_step(step, xml, kw_name, evidence_dir):
    """
    Check if is a evidence keyword, if true adds a evidence to the respective test step

    :param step: Current test step to save evidence
    :param xml: Current keyword XML element
    :param kw_name: Current keyword name
    :param evidence_dir: Directory where evidences are located
    :return:
        Boolean value, True if current keyword is a evidence Keyword, False otherwise
    """
    if kw_name in evidence_KWs:  # check if test step is in the evidence keywords (e.g. Capture Page Screenshot)

        # get msg from the evedence execution (it contains information regarding the evidence)
        evidence_msg = xml.find(constants.XPATH_EVIDENCE_MSG).text

        # get the evidence source file from the evidence message in html
        evidence_src_search = re.search(constants.SRC_REGEX, evidence_msg, re.IGNORECASE)

        # if found
        if evidence_src_search:
            # get path to the evidence
            evidence_src = os.path.join(os.path.dirname(evidence_dir), evidence_src_search.group(1))

            # opens evidence file to encode to base64
            with open(evidence_src, "rb") as evidence_file:
                evidence_base64 = base64.b64encode(evidence_file.read())
                #evidence_base64 = 'lol'

            evidence = {}
            teb.path_new(evidence, constants.EVIDENCE_DATA,evidence_base64)
            teb.path_new(evidence, constants.EVIDENCE_FILENAME, os.path.basename(evidence_src))
            
            #print evidence
            #print 'Dealing evidences:'
            #print step
            teb.path_get(step,constants.STEP_EVIDENCES).append(evidence)
            
            #print step
            #step.add_evidence(TestEvidence(evidence_base64, os.path.basename(evidence_src)))

        return True
    else:
        return False


def get_log_and_evidences_from_teststep(step_xml, teststep, xml_file):
    """
    Examine a test step to get logs or evidences and add them to test step

    :param step_xml: XML element of current step
    :param teststep: Test step class of current step
    :param xml_file: XML file

    """
    for kw_xml in step_xml.iter(constants.KW_TAG):
        # verify if is a log keyword and if positive logs the current test step
        _log_step(teststep, kw_xml, kw_xml.attrib[constants.ATTRIB_NAME])
        # verify if is a evidence keyword and if positive, saves evidence in the current test step
        _evidence_step(teststep, kw_xml, kw_xml.attrib[constants.ATTRIB_NAME], xml_file)


def _parse_test_steps(xml_file, test_xml, test, test_steps_filter, evidences_import):
    """
    Parse a test xml element and add steps to test case class

    :param xml_file: XML file
    :param test_xml: Current test xml element
    :param test: Current test class
    :param test_steps_filter: Test steps filtering
    :param evidences_import: Evidences selection
    :return: A test case class with all steps
    """
    # if any of these is TRUE it mean that we have to parse the test steps
    if test_steps_filter or evidences_import != constants.EVIDENCES_SELECTION_NONE:

        previous_step = None

        # parse XML test case steps
        for step_xml in test_xml.findall(constants.KW_TAG):

            if constants.ATTRIB_TYPE in step_xml.attrib and step_xml.attrib[constants.ATTRIB_TYPE] == constants.SETUP:
                continue

            # get test step name
            teststep_name = step_xml.attrib[constants.ATTRIB_NAME].replace("{", "\{").replace("}", "\}")

            # get test step status
            teststep_status = step_xml.find(constants.STATUS_TAG).attrib[constants.ATTRIB_STATUS]
        
            #teststep = TestStep(teststep_status)

            teststep = {}

            #   Init test step values
            teb.path_new(teststep, constants.STEP_STATUS, teststep_status)
            teb.path_new(teststep, constants.STEP_COMMENT, '')
            teb.path_new(teststep, constants.STEP_EVIDENCES, [])
            
            #print ' CURRENT STEP :'
            #print teststep

            if evidences_import == constants.EVIDENCES_SELECTION_NONE:  # if importor of evidences is None continue to next test step
                continue

            elif evidences_import == constants.EVIDENCES_SELECTION_FAIL:
                #   check for special keywords given the previous test step status. Search for log/evidence keywords and
                #   teardown
                if previous_step and teb.path_get(previous_step, 'step_status') == constants.FAIL:
                    if _log_step(previous_step, step_xml, teststep_name) or \
                            _evidence_step(previous_step, step_xml, teststep_name, xml_file):
                        continue

                    if constants.ATTRIB_TYPE in step_xml.attrib:
                        kw_type = step_xml.attrib[constants.ATTRIB_TYPE]

                        #   if a test step has failed, check if the next kw is teardown. If true, treat it as a high keyword
                        if kw_type == constants.TEARDOWN:
                            # for each keyword of the test step
                            get_log_and_evidences_from_teststep(step_xml,teststep, xml_file)
                            continue
                        else:
                            continue

                if teststep_status == constants.FAIL:   # check if the current teststep status is Fail

                    # get the ERROR message from lower KW
                    # go deep to all keywords of the test step
                    for kw in step_xml.iter(constants.KW_TAG):

                        # extract evidences given that evidences filter is Fail
                        # verify if is a log keyword and if positive logs the current test step
                        _log_step(teststep, kw, kw.attrib[constants.ATTRIB_NAME])

                        # verify if is a evidence keyword and if positive, saves evidence in the current test step
                        _evidence_step(teststep, kw, kw.attrib[constants.ATTRIB_NAME], xml_file)

                        # check if the keyword has failed
                        if kw.find(constants.STATUS_TAG).attrib[constants.ATTRIB_STATUS] == constants.FAIL:
                            # get message tags
                            for msg in kw.findall(constants.MSG_TAG):
                                # check if level is failed is the positive case it corresponds to the error message
                                if msg.attrib[constants.ATTRIB_LEVEL] == constants.FAIL:
                                    #teststep.add_to_comment('{}:{}\n'.format(msg.attrib[constants.ATTRIB_LEVEL], msg.text))
                                    teb.path_set(teststep, constants.STEP_COMMENT, teb.path_get(teststep,constants.STEP_COMMENT) + 
                                                        '{}:{}\n'.format(msg.attrib[constants.ATTRIB_LEVEL], msg.text))
            else:
                #check current keyword if it is a log/evidence kw add it to the last test step
                if _log_step(previous_step, step_xml, teststep_name) or _evidence_step(previous_step, step_xml, teststep_name, xml_file):
                    continue

                if previous_step and teb.path_get(previous_step, constants.STEP_STATUS) == constants.FAIL:
                    if constants.ATTRIB_TYPE in step_xml.attrib:
                        kw_type = step_xml.attrib[constants.ATTRIB_TYPE]

                        # if a test step has failed, check if the next kw is teardown. If true, treat it as a high keyword
                        if kw_type == constants.TEARDOWN:

                            # for each keyword of the test step
                            get_log_and_evidences_from_teststep(step_xml, teststep, xml_file)

                            continue
                        else:
                            continue

                #in case of failure get the message from lowe kw
                if teststep_status == constants.FAIL:
                    # go deep to all keywords of the test step
                    for kw in step_xml.iter(constants.KW_TAG):
                        # check if the keyword has failed
                        if kw.find(constants.STATUS_TAG).attrib[constants.ATTRIB_STATUS] == constants.FAIL:
                            # get message tags
                            for msg in kw.findall(constants.MSG_TAG):
                                # check if level is failed is the positive case it corresponds to the error message
                                if msg.attrib[constants.ATTRIB_LEVEL] == constants.FAIL:
                                    #teststep.add_to_comment('{}:{}\n'.format(msg.attrib[constants.ATTRIB_LEVEL], msg.text))
                                    teb.path_set(teststep, constants.STEP_COMMENT, teb.path_get(teststep,constants.STEP_COMMENT) + 
                                                        '{}:{}\n'.format(msg.attrib[constants.ATTRIB_LEVEL], msg.text))
                                    
                # for each keyword of the test step
                get_log_and_evidences_from_teststep(step_xml,teststep, xml_file)

            previous_step = teststep

            if test_steps_filter:
                teb.path_get(test, constants.STEPS).append(teststep)
                #test.add_step(teststep)
            else:
                teststep_evidences = teb.path_get(teststep, constants.TEST_EVIDENCES)
                test_evidences = teb.path_get(test, constants.TEST_EVIDENCES)

                test_evidences = test_evidences + teststep_evidences 
                
                teb.path_set(test, constants.TEST_EVIDENCES, test_evidences)
               # if teststep.comment:
               #     test.comment += teststep.comment

    return test


def _create_test_case(test_xml, test_key):
    """
    Create a test case class given the xml and the JIRA ISSUE
    :param test_xml: Current test XML element
    :param test_key: Test key of the test to create
    :return: A test case class
    """
    # get test status
    test_status_elem = test_xml.find(constants.STATUS_TAG)
    test_status_value = test_status_elem.attrib[constants.ATTRIB_STATUS]
    test_status_text = test_xml.find(constants.STATUS_TAG).text

    # get stat date time
    test_start_date = datetime.strptime(test_status_elem.attrib[constants.ATTRIB_STARTTIME],
                                        constants.DATE_ROBOT_FRAMEWORK_FORMAT).strftime(constants.DATE_XRAY_FORMAT)
    # get end date time
    test_finish_date = datetime.strptime(test_status_elem.attrib[constants.ATTRIB_ENDTIME],
                                         constants.DATE_ROBOT_FRAMEWORK_FORMAT).strftime(constants.DATE_XRAY_FORMAT)

    test = {}

    teb.path_new(test,constants.TEST_TESTKEY, test_key)
    teb.path_new(test,constants.TEST_STATUS, test_status_value)
    teb.path_new(test,constants.TEST_START, test_start_date)
    teb.path_new(test,constants.TEST_FINISH, test_finish_date)
    teb.path_new(test,constants.STEPS, [])
    if test_status_text:
        teb.path_new(test,constants.TEST_COMMENT, test_status_text)
    
    #print test
    '''
    # create a new TestClass object
    test = TestCase(test_key, test_status_value)
    test.start = test_start_date
    test.finish = test_finish_date
    if test_status_text:
        test.comment = test_status_text
    '''
    return test, test_key


def _parse_test(element, tag_filter, filter_tests, test_steps_filter, evidences_import, xml_file, debug_mode):
    """
    Parse a test case XML element and create a Test Case class with its steps
    :param element: Current test XML element
    :param tag_filter: Filtering of tags
    :param filter_tests: Dict to add the filtered tests
    :param test_steps_filter: Filtering of test steps
    :param evidences_import: Evidences selection
    :param xml_file: XML file
    :return: A test case class with all its steps; a JIRA test execution key if found
    """
    tag_found = ''
    testexec_key = constants.NO_TESTEXEC_KEY
    test_key = ''
    tags_text = element.xpath(constants.XPATH_TAG_TEXT)

    for tag_text in tags_text:

        if tag_filter:
            if tag_text in import_filters[constants.FILTER_TAG_KEY]:
                tag_found = tag_text
        try:
            jira_issue_type , jira_issue_number = tag_text.split(constants.TEST_TAG_SEPARATOR)
            # verify if tag has the label JIRA_TEST
            if constants.JIRA_TEST_TAG == jira_issue_type:
                test_key = jira_issue_number  # extract tag value
                # print tag_text
                # verify if tag has the label JIRA_TESTEXEC
            if constants.JIRA_TESTEXEC_TAG == jira_issue_type:
                testexec_key = jira_issue_number
        except ValueError:
            if debug_mode:
                print "TAG: " + tag_text + " Skipped"

    test_case, test_key = _create_test_case(element, test_key)
    test_case = _parse_test_steps(xml_file, element, test_case, test_steps_filter,
                                  evidences_import)  # create a test case object and adds steps to it

    if tag_filter:
        if tag_found:
            filter_tests[constants.FILTER_TAG_KEY].append(test_case)

    return test_case, test_key, testexec_key


def _get_test_date(element, date_attrib):
    status = element.find(constants.STATUS_TAG)
    if status is not None:
        if status.attrib[constants.ATTRIB_ENDTIME] != constants.NO_VALUE:
            # get end date time
            return datetime.strptime(status.attrib[date_attrib],
                                                  constants.DATE_ROBOT_FRAMEWORK_FORMAT).strftime(
                constants.DATE_XRAY_FORMAT)


def filtering_import(xml_file, test_steps_filter, evidences_import, import_filters, filter_option, debug_mode, **kwargs):
    """
    Imports with filtering and return a test execution
    :param xml_file: Robot Framework output XML file
    :param test_steps_filter: Filtering of test steps
    :param evidences_import: Evidences Selection
    :param import_filters: Importation filters
    :param filter_option: Filter option, either intersaction or union
    :return: Test execution with the filters applied
    """
    filters_tests = {}

    test_suite_filter = False
    test_case_filter = False
    tag_filter = False

    if constants.FILTER_TEST_SUITE_KEY in import_filters:
        test_suite_filter = True
        filters_tests[constants.FILTER_TEST_SUITE_KEY] = []

    if constants.FILTER_TEST_CASE_KEY in import_filters:
        test_case_filter = True
        filters_tests[constants.FILTER_TEST_CASE_KEY] = []

    if constants.FILTER_TAG_KEY in import_filters:
        tag_filter = True
        filters_tests[constants.FILTER_TAG_KEY] = []


    tests = []
    test_execs = {}
    test_testexec_key = {}
    name = ''

    for _, element in ET.iterparse(xml_file, tag=(constants.TEST_TAG, constants.SUITE_TAG)):

        if element.tag == constants.TEST_TAG:
            test_case, test_key, testexec_key = _parse_test(element, tag_filter, filters_tests, test_steps_filter,
                                                  evidences_import, xml_file,debug_mode)

            test_testexec_key[test_key] = testexec_key

            if test_case_filter:
                if element.attrib[constants.ATTRIB_NAME] in import_filters[constants.FILTER_TEST_CASE_KEY]:
                    filters_tests[constants.FILTER_TEST_CASE_KEY].append(test_case)
            tests.append(test_case)

        if element.tag == constants.SUITE_TAG and constants.ATTRIB_NAME in element.attrib:
            if test_suite_filter:
                for ancestor in element.xpath(constants.XPATH_ANCESTOR):
                    if constants.ATTRIB_NAME in ancestor.attrib:
                        if ancestor.attrib[constants.ATTRIB_NAME] in import_filters[constants.FILTER_TEST_SUITE_KEY]:
                            filters_tests[constants.FILTER_TEST_SUITE_KEY] += tests

            tests = []

        # get test execution name
        if not name:
            for ancestor in element.xpath(constants.XPATH_ANCESTOR_SUITE):
                name = ancestor.attrib[constants.ATTRIB_NAME]
                break

        element.clear()
        for ancestor in element.xpath(constants.XPATH_ANCESTOR):
            while ancestor.getprevious() is not None:
                del ancestor.getparent()[0]

    if test_suite_filter or test_case_filter or tag_filter:
        filter_key_value = []
        tests = []
        for key, value in import_filters.items():
            value_filters = '_'.join(value)
            filter_key_value.append('{}_{}'.format(key, value_filters))
            tests.append(set(filters_tests[key]))

        if filter_option == constants.FILTER_OPTION_AND:
            result = reduce(set.intersection, tests)
        else:
            result = reduce(set.union,tests)

        result = sorted(list(result), key=lambda test: test.testKey)

        for test in result:
            testexec_key = test_testexec_key[teb.path_get(test, constants.TEST_TESTKEY)]
            if testexec_key in test_execs:
                test_execs[testexec_key].tests.append(test)
            else:
                test_exec = {}
                teb.path_new(test_exec, constants.TESTS, [tests])
                
                #test_exec = TestExec([test])
                
                if testexec_key != constants.NO_TESTEXEC_KEY:
                    #test_exec.testExecutionKey = testexec_key
                    teb.path_new(test_exec,constants.TESTEXECUTIONKEY, testexec_key)
                else:


                    #test_exec_info = TestExecInfo(**kwargs)

                    teb.path_new(test_exec,constants.SUMMARY, name + ':'.join(filter_key_value) + '-' +
                                                                           str(time.time()))
                    for key in kwargs:
                        teb.path_new(test_exec, key, kwargs[key])


                    #test_exec_info.summary = test_exec_info.summary.format(name, ':'.join(filter_key_value) + '-' +
                    #                                                       str(time.time()))
                   
                    #test_exec.info = test_exec_info

                test_execs[testexec_key] = test_exec
    return test_execs


def no_filtering_import(xml_file, test_steps_filter, evidences_import, debug_mode, **kwargs):
    """
    Import XML file with no filtering
    :param xml_file: Robot Framework XML output file
    :param test_steps_filter: Filtering of test steps
    :param evidences_import: Evidences selection
    :return: Test executions to import
    """
    test_execs = {}
    for _, element in ET.iterparse(xml_file, tag=(constants.TEST_TAG, constants.SUITE_TAG)):

        if element.tag == constants.TEST_TAG:
            test_case, _, testexec_key = _parse_test(element, False, {},
                                                  test_steps_filter, evidences_import, xml_file, debug_mode)
            #print test_execs
            #print testexec_key
            if testexec_key in test_execs:
                #print test_execs[testexec_key]
                test_execs[testexec_key]['tests'].append(test_case)
            else:
                #   print test
                test_exec = {}
                teb.path_new(test_exec, constants.TESTS, [test_case])


                if testexec_key != constants.NO_TESTEXEC_KEY:
                    test_exec['testExecutionKey'] = testexec_key

                #test_exec_info = TestExecInfo(**kwargs)
                #print kwargs
                for key in kwargs:
                    teb.path_new(test_exec, key, kwargs[key])
        
                # If does not have startDate 
                if teb.path_get(test_exec, constants.TEST_EXECUTION_INFO_STARTDATE_KEY) is None:
                    teb.path_new(test_exec,constants.TEST_EXECUTION_INFO_STARTDATE_KEY, _get_test_date(element, constants.ATTRIB_STARTTIME))
        
                # If does not have finishDate
                if teb.path_get(test_exec, constants.TEST_EXECUTION_INFO_FINISHDATE_KEY) is None:
                    teb.path_new(test_exec,constants.TEST_EXECUTION_INFO_FINISHDATE_KEY, _get_test_date(element, constants.ATTRIB_STARTTIME))
                #if not hasattr(test_exec_info, constants.TEST_EXECUTION_INFO_STARTDATE_KEY):
                #    test_exec_info.startDate = _get_test_date(element, constants.ATTRIB_STARTTIME)
        
                #if not hasattr(test_exec_info, constants.TEST_EXECUTION_INFO_FINISHDATE_KEY):
                #    test_exec_info.finishDate = _get_test_date(element, constants.ATTRIB_ENDTIME)

                name = ''
                for ancestor in element.xpath(constants.XPATH_ANCESTOR_SUITE):
                    name = ancestor.attrib[constants.ATTRIB_NAME]
                    break

        
                teb.path_new(test_exec,constants.SUMMARY, name + ' ' + str(time.time()))

                #test_exec_info.summary = test_exec_info.summary.format(name + ' ' + str(time.time()))
                #test_exec.info = test_exec_info
                test_execs[testexec_key] = test_exec

        element.clear()
        for ancestor in element.xpath(constants.XPATH_ANCESTOR):
            while ancestor.getprevious() is not None:
                del ancestor.getparent()[0]

    return test_execs

def send_request(test_exec, new_test_exec, cert, oauth_client, debug_mode):
    """
    Sends a request to import test execution via JIRA-XRAY API

    :param data: JSON data
    :return:
        Test Execution Key
    """
    headers = {constants.CONTENT_TYPE: constants.CONTENT_TYPE_JSON}
    url = urljoin(jira_address, endpoint)
    try:
        #   If this exists it mean that we have to create a Test Execution first
        if new_test_exec:
            json_new_test_exec = json.dumps(new_test_exec)
            if debug_mode:
                print json_new_test_exec
            if oauth_client is None:
                #   Create a new issue
                response = requests.post(urljoin(jira_address,'rest/api/2/issue'), headers=headers, data = json_new_test_exec, auth=(username,password),verify = cert)
            else:
                response, content = oauth_client.request(urljoin(jira_address, 'rest/api/2/issue'), method="POST", headers=headers, body = json_new_test_exec)
                if response['status'] != '200':
                    raise Exception(constants.OAUTH_EXCEPTION_MSG.format(response['status'], content))
            if debug_mode:
                print response
                resp_test = getattr(response,'text')
                if resp_test:
                    print response.text

            response.raise_for_status()
            #   Get Key from the created Issu and add it to the Test Execution JSON in order to update the empty issue recently created
            teb.path_set(test_exec, constants.TESTEXECUTIONKEY, response.json().get('key'))
        
        json_test_exec = json.dumps(test_exec)
        if debug_mode:
            with open('dump.json', 'w') as f:
                json.dump(test_exec,f)
        #   Try basic auth if no OAuth client
        if oauth_client is None:
            response = requests.post(url, headers=headers, data=json_test_exec, auth=(username, password), verify = cert)
            if debug_mode:
                print response.text
                print response
            response.raise_for_status()
            return response.text
        else:
            resp, content = oauth_client.request(url, method="POST", body = json_test_exec, headers = headers)
            if resp['status'] != '200':
                raise Exception(constants.OAUTH_EXCEPTION_MSG.format(resp['status'], content))
            return content

    except Exception as e:
        print 'exception: '
        print e.message
        sys.exit(1)

if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description=constants.DESCRIPTION.encode('utf-8'),
        epilog=constants.EPILOG,
        formatter_class=RawTextHelpFormatter
    )

    parser.add_argument(constants.FILE, help=constants.FILE_HELP)
    parser.add_argument(constants.URL, help=constants.URL_HELP)
    parser.add_argument(constants.USERNAME, help=constants.USERNAME_HELP)
    
    parser.add_argument(constants.PASSWORD, constants.PASSWORD_EXTENDED, help=constants.PASSWORD_HELP)

    parser.add_argument(constants.NO_STEPS, constants.NO_STEPS_EXTENDED, action=constants.NO_STEPS_ACTION,
                        help=constants.NO_STEPS_HELP)

    parser.add_argument(constants.ENDPOINT, constants.ENDPOINT_EXTENDED,
                        default=constants.ENDPOINT_DEFAULT, help=constants.ENDPOINT_HELP)

    parser.add_argument(constants.FILTER_TAG, constants.FILTER_TAG_EXTENDED, help=constants.FILTER_TAG_HELP,
                        action=constants.FILTER_TAG_ACTION)

    parser.add_argument(constants.FILTER_TEST_SUITE, constants.FILTER_TEST_SUITE_EXTENDED,
                        help=constants.FILTER_TEST_SUITE_HELP, action=constants.FILTER_TEST_SUITE_ACTION)

    parser.add_argument(constants.FILTER_TEST_CASE, constants.FILTER_TEST_CASE_EXTENDED,
                        help=constants.FILTER_TEST_CASE_HELP, action=constants.FILTER_TEST_CASE_ACTION)

    parser.add_argument(constants.FILTER_OPTION, constants.FILTER_OPTION_EXTENDED,
                        default=constants.FILTER_OPTION_DEFAULT, help=constants.FILTER_OPTION_HELP)

    parser.add_argument(constants.EVIDENCES_SELECTION, constants.EVIDENCES_SELECTION_EXTENDED,
                        default=constants.EVIDENCES_SELECTION_DEFAULT, help=constants.EVIDENCES_SELECTION_HELP)

    parser.add_argument(constants.DEBUG, constants.DEBUG_EXTENDED, action=constants.DEBUG_ACTION,
                        help=constants.DEBUG_HELP)

    parser.add_argument(constants.TEST_EXEC_SUMMARY, constants.TEST_EXEC_SUMMARY_EXTENDED,
                        help=constants.TEST_EXEC_SUMMARY_HELP)

    parser.add_argument(constants.TEST_EXEC_DESCRIPTION,constants.TEST_EXEC_DESCRIPTION_EXTENDED,
                        help=constants.TEST_EXEC_DESCRIPTION_HELP)

    parser.add_argument(constants.TEST_EXEC_VERSION, constants.TEST_EXEC_VERSION_EXTENDED,
                        help=constants.TEST_EXEC_VERSION_HELP)

    parser.add_argument(constants.TEST_EXEC_REVISION, constants.TEST_EXEC_REVISION_EXTENDED,
                        help=constants.TEST_EXEC_REVISION_HELP)

    parser.add_argument(constants.TEST_EXEC_USER, constants.TEST_EXEC_USER_EXTENDED,
                        help=constants.TEST_EXEC_USER_HELP)

    parser.add_argument(constants.TEST_EXEC_STARTDATE, constants.TEST_EXEC_STARTDATE_EXTENDED,
                        help=constants.TEST_EXEC_STARTDATE_HELP)

    parser.add_argument(constants.TEST_EXEC_FINISHDATE, constants.TEST_EXEC_FINISHDATE_EXTENDED,
                        help=constants.TEST_EXEC_FINISHDATE_HELP)

    parser.add_argument(constants.TEST_EXEC_TESTPLANKEY, constants.TEST_EXEC_TESTPLANKEY_EXTENDED,
                        help=constants.TEST_EXEC_TESTPLANKEY_HELP)

    parser.add_argument(constants.TEST_EXEC_TESTENV, constants.TEST_EXEC_TESTENV_EXTENDED,
                        help=constants.TEST_EXEC_TESTENV_HELP)
    
    parser.add_argument(constants.CERTIFICATE, constants.CERTIFICATE_EXTENDED,
                        help=constants.CERTIFICATE_HELP)

    parser.add_argument(constants.COMPONENTS, constants.COMPONENTS_EXTENDED, nargs='+',
                        help=constants.COMPONENTS_HELP)

    # steps_filter == false ? do not import steps : import steps
    # evidences => NONE || FAIL || ALL
    # NONE => No evidences
    # FAIL => Import evidences of Failed steps
    # ALL => Improt all evidences

    args = parser.parse_args()

    # output XML file
    file = args.file

    # JIRA server configuration
    jira_address = args.url   # 'http://10.12.7.54:8080'  # CHANGE
    endpoint = args.endpoint  # '/rest/raven/1.0/import/execution'
    username = args.username  
    password = args.password 

    # Test Filtering, filters output file to only import the required test execution.

    # filter test steps
    test_steps_filter = args.no_steps  # boolean value

    import_filters = {}

    # filter tests by tag
    filter_tag = args.filter_tag
    if filter_tag:
        import_filters[constants.FILTER_TAG_KEY] = filter_tag  # list with tag filters

    # filter tests by test suite name
    filter_test_suite = args.filter_test_suite
    if filter_test_suite:
        import_filters[constants.FILTER_TEST_SUITE_KEY] = filter_test_suite  # list with test suite filters

    # filter tests by test case name
    filter_test_case = args.filter_test_case
    if filter_test_case:
        import_filters[constants.FILTER_TEST_CASE_KEY] = filter_test_case  # list with test case filters

    # option for the relationship between filters
    filter_option = args.filter_options

    # filter evidences. None; Fail only; or All
    evidences_import = args.evidences_selection

    # debug flag
    debug_mode = args.debug

    # path to certicate
    certificate = args.certificate if args.certificate else False

    # Test Execution Info
    test_exec_info_values = {}

    if username:
        test_exec_info_values[constants.TEST_EXECUTION_INFO_USER_KEY] = username

    if args.summary:
        test_exec_info_values[constants.TEST_EXECUTION_INFO_SUMMARY_KEY] = args.summary

    if args.description:
        test_exec_info_values[constants.TEST_EXECUTION_INFO_DESCRIPTION_KEY] = args.description

    if args.test_exec_version:
        test_exec_info_values[constants.TEST_EXECUTION_INFO_VERSION_KEY] = args.test_exec_version

    if args.user:
        test_exec_info_values[constants.TEST_EXECUTION_INFO_USER_KEY] = args.user

    if args.test_exec_revision:
        test_exec_info_values[constants.TEST_EXECUTION_INFO_REVISION_KEY] = args.test_exec_revision

    if args.start_date:
        test_exec_info_values[constants.TEST_EXECUTION_INFO_STARTDATE_KEY] = args.start_date

    if args.finish_date:
        test_exec_info_values[constants.TEST_EXECUTION_INFO_FINISHDATE_KEY] = args.finish_date

    if args.test_plan_key:
        test_exec_info_values[constants.TEST_EXECUTION_INFO_TESTPLANKEY_KEY] = args.test_plan_key

    if args.test_environments:
        test_exec_info_values[constants.TEST_EXECUTION_INFO_TESTENVIRONMENTS_KEY] = args.test_environments.\
            split(constants.TEST_EXECUTION_INFO_TESTENVIRONMENTS_SEPERATOR)

    #   Just make sure that if no components are inserted, the components list is empty
    if args.components is None:
        args.components = []

    # start_time = time.time()

    if filter_test_suite or filter_test_case or filter_tag:
        if constants.TEST_EXECUTION_INFO_SUMMARY_KEY not in test_exec_info_values:
            test_exec_info_values[constants.TEST_EXECUTION_INFO_SUMMARY_KEY] = constants.TEST_EXECUTION_SUMMARY_FILTERS

        test_execs = filtering_import(file, test_steps_filter,
                                      evidences_import, import_filters, filter_option,  debug_mode, **test_exec_info_values)
    else:

        if constants.TEST_EXECUTION_INFO_SUMMARY_KEY not in test_exec_info_values:
            test_exec_info_values[constants.TEST_EXECUTION_INFO_SUMMARY_KEY] = constants.TEST_EXECUTION_SUMMARY

        test_execs = no_filtering_import(file, test_steps_filter, evidences_import,  debug_mode, **test_exec_info_values)

    # print time.time() - start_time

    # if no password create a OAuth client

    oauth_client = None 
    if not password:
        oauth_client = rfw2xray_auth.create_oauth_client(os.path.join(os.path.dirname(os.path.abspath(__file__)), constants.OAUTH_CONFIG_FILE))

    for key, test_exec in test_execs.items():
        new_test_exec = {}
        #   Check if script was initialized with components, if that is the case then create an Empty Test Execution.
        if args.components:
            #   Get project key
            project_key = teb.path_get(test_exec,constants.PROJECT)

            #   Project key migh not be referenced in Test Exec JSON, then go get from the first test Key.
            project_key = teb.path_get(teb.path_get(test_exec, constants.TESTS)[0],constants.TEST_TESTKEY).split('-')[0]

            new_test_exec = {
                "fields": {
                    "project": {
                        "key": project_key
                    },
                    "summary": teb.path_get(test_exec,constants.SUMMARY),
                    "issuetype":{
                        "name": "Test Execution"
                    },
                    "components": [{"name": component_name } for component_name in args.components ]
                }
            }

        response = send_request(test_exec, new_test_exec, certificate, oauth_client, debug_mode)
        if response:
            json_response = json.loads(response)
            if debug_mode:
                test_keys = []
                print json_response
            test_exec_key = json_response[constants.TEST_EXEC_ISSUE][constants.KEY]
            print test_exec_key
