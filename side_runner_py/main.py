import sys
import os.path
import json
import time
import glob
import traceback
import datetime
import contextlib
from pathlib import Path

from selenium.webdriver.common.alert import Alert
from selenium.common.exceptions import UnexpectedAlertPresentException, NoAlertPresentException

from .commands import TEST_HANDLER_MAP
from .utils import with_retry
from .init import initialize
from .config import Config
from .side import SIDEProjectManager
from .hook import hook_context
from .variable import VariableStore
from .exceptions import AssertionFailure, VerificationFailure

from .log import getLogger
logger = getLogger(__name__)


def get_screenshot(driver, test_suite_name, test_case_name, cmd_index, test_dict, outdir):
    try:
        filename = "_".join([test_suite_name, test_case_name, "{0:02d}".format(cmd_index), test_dict['id']]) + ".png"
        driver.get_screenshot_as_file(os.path.join(outdir, filename))
    except UnexpectedAlertPresentException:
        logger.warning("Unable to get Screenshot due to alert present")
    except Exception:
        logger.warning(traceback.format_exc())


def _format_test_command_output(test, is_failed, is_verify_failed, failed_msg, failed_type):
    # generate test result
    return {
        'comment': test.get('comment'),
        'command': test['command'],
        'target': test['target'],
        'value': test['value'],
        'is_failed': is_failed,
        'is_verify_failed': is_verify_failed,
        'failed_msg': failed_msg,
        'failed_type': failed_type,
    }


def execute_test_command(session_manager, test_project, test_suite, test_dict):
    try:
        handler_func = TEST_HANDLER_MAP[test_dict['command']]
        handler_func(session_manager.driver, session_manager.variable_store, test_project, test_suite, test_dict)
    except VerificationFailure as exc:
        return _format_test_command_output(test_dict, False, True, exc.format_msg(), 'verify')
    except AssertionFailure as exc:
        logger.warning(exc.format_msg())
        return _format_test_command_output(test_dict, True, False, exc.format_msg(), 'assert')
    except Exception:
        traceback_msg = traceback.format_exc()
        logger.warning(traceback_msg)
        return _format_test_command_output(test_dict, True, False, traceback_msg, 'unknown')
    return _format_test_command_output(test_dict, False, False, '', '')


def _ensure_test_output_by_id(output, some_id, create):
    f = [elm for elm in output if elm['id'] == some_id]
    if f:
        return f[0]

    # create if not found test_suite output element
    output.append(create)
    return create


def _store_test_command_output(output, test_suite, tests, test_command_output):
    # ensure and get output dict referenct
    test_suite_output = _ensure_test_output_by_id(
        output, test_suite['id'], {'name': test_suite['name'], 'tests': [], 'id': test_suite['id']})
    tests_output = _ensure_test_output_by_id(
        test_suite_output['tests'], tests['id'], {'name': tests['name'], 'commands': [], 'id': tests['id']})
    # store test-command output
    tests_output['commands'].append(test_command_output)


@contextlib.contextmanager
def _prepare_test_project_execution(session_manager, test_project):
    # hold test execute time
    now = datetime.datetime.now()
    execute_datetime = now.replace(microsecond=0).isoformat().replace(':', '-').replace('T', '.')

    # prepare output directory
    outdir = Path(Config.OUTPUT_DIR) / execute_datetime
    outdir.mkdir(parents=True, exist_ok=True)

    output = []
    try:
        with hook_context('project', session_manager, test_project):
            # execute test
            yield output, outdir

    finally:
        # output test result
        with open(outdir / 'result.json', 'w') as f:
            json.dump(output, f, indent=4)


class SessionManager():
    def __init__(self):
        self.driver = None
        self.variable_store = VariableStore()

    def _close_driver_gracefully(self):
        if Config.CLOSE_METHOD == 'close':
            try:
                self.driver.close()
            except UnexpectedAlertPresentException:
                try:
                    Alert(self.driver).accept()
                except NoAlertPresentException:
                    pass
                self.driver.close()
            except Exception:
                logger.warning('Unable to close driver')
                logger.warning(traceback.format_exc())
        elif Config.CLOSE_METHOD == 'quit':
            try:
                self.driver.quit()
            except Exception:
                logger.warning('Unable to close driver')
                logger.warning(traceback.format_exc())
        else:
            logger.error('Unknown close method: {}'.format(Config.CLOSE_METHOD))
            sys.exit(1)

    def _close_driver_or_skip(self):
        logger.info('Close session {}'.format(self.driver))
        if self.driver is not None:
            self._close_driver_gracefully()
            self.driver = None

    def _reset_variable_store(self):
        self.variable_store = VariableStore()

    @contextlib.contextmanager
    def _test_suite_session(self, test_project, test_suite):
        def _():
            for test_id in test_suite['tests']:
                yield test_id

        try:
            logger.debug('Enter test-suite {}'.format(test_suite['id']))
            with hook_context('suite', self, test_project, test_suite):
                yield _
        except AssertionFailure:
            pass
        except Exception:
            traceback_msg = traceback.format_exc()
            logger.warning(traceback_msg)
        finally:
            logger.debug('Leave test-suite {}'.format(test_suite['id']))

        # reset variable store and close driver on test_suite execution finished
        self._reset_variable_store()
        self._close_driver_or_skip()

    @contextlib.contextmanager
    def _tests_session(self, test_project, test_suite, tests, test_id):
        def _():
            for idx, test in enumerate(tests[test_id]['commands']):
                yield idx, test

        # prepare webdriver
        logger.debug('Using session {}'.format(self.driver))
        if self.driver is None:
            self.driver = with_retry(Config.DRIVER_RETRY_COUNT, Config.DRIVER_RETRY_WAIT,
                                     initialize, Config.WEBDRIVER_URL)
            logger.info('Create session {}'.format(self.driver))

        try:
            logger.debug('Enter tests {}'.format(test_id))
            with hook_context('test', self, test_project, test_suite, tests[test_id]):
                yield _
        except Exception as exc:
            if not test_suite.get('persistSession', False):
                self._reset_variable_store()
                self._close_driver_or_skip()
                return
            raise exc
        finally:
            logger.debug('Leave tests {}'.format(test_id))

        # reset variable store and close driver if test_suite require session close
        if not test_suite.get('persistSession', False):
            self._reset_variable_store()
            self._close_driver_or_skip()


def _execute_test_command(session_manager, test_project, test_suite, test, idx, test_command, output, outdir):
    logger.debug('Using session {}'.format(session_manager.driver))

    # log test-command
    test_path_str = '{}.{}.{}.{}'.format(test_suite['name'], test['name'], idx, test_command['command'])
    logger.info('TEST: {} to {} with {}'.format(test_path_str, test_command['target'], test_command['value']))

    get_screenshot(session_manager.driver, test_suite['name'], test['name'], idx, test_command, outdir)

    # execute test command
    with hook_context('command', session_manager, test_project, test_suite, test, test_command, idx):
        command_output = execute_test_command(session_manager, test_project, test_suite, test_command)
        _store_test_command_output(output, test_suite, test, command_output)
        time.sleep(float(Config.DRIVER_COMMAND_WAIT) / 1000)

    if command_output['is_failed']:
        get_screenshot(session_manager.driver, test_suite['name'], test['name'], idx, test_command, outdir)
        if command_output['failed_type'] == 'assert':
            raise AssertionFailure()
        else:
            raise Exception(command_output)


def _execute_side_file(session_manager, side_manager, project_id):
    test_project, test_suites, tests = side_manager.get_project(project_id)

    with _prepare_test_project_execution(session_manager, test_project) as (output, outdir):
        for test_suite in test_suites:
            with session_manager._test_suite_session(test_project, test_suite) as gen_tests:
                for test_id in gen_tests():
                    with session_manager._tests_session(test_project, test_suite, tests, test_id) as gen_test_command:
                        for idx, test_command in gen_test_command():
                            _execute_test_command(session_manager,
                                                  test_project, test_suite, tests[test_id],
                                                  idx, test_command, output, outdir)


def _get_side_file_list_by_glob(pattern):
    # get SIDE file and param file absolute path pair
    for side_file_fullpath in [Path(p).resolve() for p in glob.glob(pattern)]:
        extentions = ['json', 'yml', 'yaml']
        param_file_fullpaths = [side_file_fullpath.parent / '{}_params.{}'.format(side_file_fullpath.stem, ext)
                                for ext in extentions]
        for param_file_fullpath in param_file_fullpaths:
            if param_file_fullpath.exists():
                yield (side_file_fullpath, param_file_fullpath)
                break
        else:
            yield (side_file_fullpath, None)


def main():
    # load and evaluate config, env, defaults
    Config.init()

    Config.WEBDRIVER_URL = "https://meeshkan.com"

    # pre-load all tests
    side_manager = SIDEProjectManager()
    fname = "./check_repos.side"
    with open(fname) as f:
        project = json.load(f)
    #for test_file_pattern in Config.TEST_FILE:
    loaded_projects = [
            (side_manager.add_project(project, None), "a", None)
        ]

    # execute test projects
    session_manager = SessionManager()
    for (project_id, side_filename, param_filename) in loaded_projects:
        logger.info('Enter test-project {} ({} {})'.format(project_id, side_filename, param_filename))
        _execute_side_file(session_manager, side_manager, project_id)
        logger.info('Leave test-project {} ({} {})'.format(project_id, side_filename, param_filename))


if __name__ == '__main__':
    main()
