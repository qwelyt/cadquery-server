import os
import os.path as op
import sys
import traceback
import importlib
from typing import List, Tuple


IGNORE_FILE_NAME = '.cqsignore'


class ModuleManager:
    def __init__(self, target: str):
        if op.isfile(target):
            self.target_is_dir = False
            self.modules_dir = op.abspath(op.dirname(target))
            self.module_name = op.basename(target[:-3])
        elif op.isdir(target):
            self.target_is_dir = True
            self.modules_dir = op.abspath(target)
            self.module_name = None
        else:
            raise ModuleManagerError('No file or folder found at "%s".' % target)

        self.modules = {}
        self.last_timestamp = 0
        self.ignored_files = []

    def init(self) -> None:
        print('Importing CadQuery...', end=' ', flush=True)
        import cadquery
        print('done.')

        sys.path.insert(1, self.modules_dir)
        self.update_ignore_list()

    def update_ignore_list(self) -> None:
        ignore_file_path = op.join(self.modules_dir, IGNORE_FILE_NAME)

        if op.isfile(ignore_file_path):
            import glob

            with open(ignore_file_path) as ignore_file:
                for line in ignore_file.readlines():
                    line = line.strip()
                    if line and not line.startswith('#'):
                        ignore = op.join(self.modules_dir, line)
                        self.ignored_files += glob.glob(ignore)

    def get_modules_path(self) -> List[str]:
        modules_path = []
        for file_name in os.listdir(self.modules_dir):
            file_path = op.join(self.modules_dir, file_name)
            if op.isfile(file_path) \
                    and op.splitext(file_path)[1] == '.py' \
                    and file_path not in self.ignored_files:
                modules_path.append(file_path)
        return modules_path

    def get_most_recent_module_info(self) -> Tuple[str, str]:
        most_recent_module_path = ''
        most_recent_timestamp = 0

        if self.target_is_dir:
            for module_path in self.get_modules_path():
                timestamp = op.getmtime(module_path)
                if timestamp > most_recent_timestamp:
                    most_recent_module_path = module_path
                    most_recent_timestamp = timestamp
        else:
            most_recent_module_path = op.join(self.modules_dir, self.module_name + '.py')
            most_recent_timestamp = op.getmtime(most_recent_module_path)

        return most_recent_module_path, most_recent_timestamp

    def get_last_updated_file(self) -> str:
        module_path, timestamp = self.get_most_recent_module_info()

        if self.last_timestamp == 0:
            self.last_timestamp = timestamp
            return ''

        if self.last_timestamp != timestamp:
            print('File %s updated.' % module_path)
            self.last_timestamp = timestamp
            return module_path

    def get_model(self) -> list:
        self.load_module()

        UI = self.get_ui_class()
        model = UI.get_model()

        if not model:
            raise ModuleManagerError('There is no object to show. Missing show_object()?')

        return model

    def load_module(self) -> None:
        if self.module_name not in self.get_modules_name():
            raise ModuleManagerError('Module "%s" is not available in the current context.' % self.module_name)

        try:
            if self.module_name in sys.modules:
                print('Reloading module %s...' % self.module_name)
                importlib.reload(self.modules[self.module_name])
            else:
                print('Importing module %s...' % self.module_name)
                self.modules[self.module_name] = importlib.import_module(self.module_name)

        except Exception as error:
            raise ModuleManagerError(type(error).__name__ + ': ' + str(error), traceback.format_exc())

    def get_data(self) -> dict:
        data = {}

        if self.module_name:
            try:
                data = {
                    'module_name': self.module_name,
                    'model': self.get_model()
                }
            except ModuleManagerError as error:
                data={
                    'error': error.message,
                    'stacktrace': error.stacktrace
                }

        return data

    def get_modules_name(self) -> List[str]:
        return [ op.basename(path)[:-3] for path in self.get_modules_path() ]

    def get_ui_class(self) -> type:
        try:
            return getattr(self.modules[self.module_name], 'UI')
        except AttributeError:
            raise ModuleManagerError('UI class is not imported. '
                + 'Please add `from cq_server.ui import UI, show_object` '
                + 'at the begining of the script.')


class ModuleManagerError(Exception):
    def __init__(self, message: str, stacktrace: str=''):
        self.message = message
        self.stacktrace = stacktrace

        print('Module manager error: ' + message, file=sys.stderr)
        if stacktrace:
            print(stacktrace, file=sys.stderr)

        super().__init__(self.message)
