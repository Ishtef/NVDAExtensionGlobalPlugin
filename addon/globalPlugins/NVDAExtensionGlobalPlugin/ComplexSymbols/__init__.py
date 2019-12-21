#NVDAExtensionGlobalPlugin/ComplexSymbols/__init__
#A part of NVDAExtensionGlobalPlugin add-on
#Copyright (C) 2018  paulber19
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

import addonHandler
addonHandler.initTranslation()
from logHandler import log
import time
import wx
import api
from keyboardHandler import KeyboardInputGesture
import ui
import speech
import gui
from gui import guiHelper
import queueHandler
import core
import config
import sys
from . import symbols
from ..utils.py3Compatibility import py3
from ..utils.NVDAStrings import NVDAString
from ..utils import  speakLater, isOpened, makeAddonWindowTitle

_lastUsedSymbols = []

if  py3:
	from api import copyToClip
else:
	# NVDA copyToClip function modified to accept non breaking space symbols
	def copyToClip(text):
		"""Copies the given text to the windows clipboard.
		@returns: True if it succeeds, False otherwise.
		@rtype: boolean
		@param text: the text which will be copied to the clipboard
		@type text: string
		"""
		import win32con
		import win32clipboard
		if isinstance(text,basestring) and len(text)>0:
			if len(text) == 1 and ord(text) == 160:
				goodToCopy = True
			elif not text.isspace():
				goodToCopy = True
			else:
				goodToCopy = False
	
		#if isinstance(text,basestring) and len(text)>0 and not text.isspace():
		if goodToCopy:
			try:
				win32clipboard.OpenClipboard()
			except win32clipboard.error:
				return False
			try:
				win32clipboard.EmptyClipboard()
				win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
			finally:
				win32clipboard.CloseClipboard()
			win32clipboard.OpenClipboard() # there seems to be a bug so to retrieve unicode text we have to reopen the clipboard
			try:
				got = 	win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
			finally:
				win32clipboard.CloseClipboard()
			if got == text:
				return True
		return False


def SendKey(keys):
	KeyboardInputGesture.fromName(keys).send()

class complexSymbolsDialog(wx.Dialog):
	shouldSuspendConfigProfileTriggers = True
	_instance = None
	title = None

	
	def __new__(cls, *args, **kwargs):
		if complexSymbolsDialog._instance is not None:
			return complexSymbolsDialog._instance
		return wx.Dialog.__new__(cls)
	
	def __init__(self, parent, symbolsManager):
		if complexSymbolsDialog._instance is not None:
			return
		complexSymbolsDialog._instance = self
		# Translators: This is the title of complex symbols dialog window.
		dialogTitle = _("Help for Complex symbols edition")
		title = complexSymbolsDialog.title = makeAddonWindowTitle(dialogTitle)
		super(complexSymbolsDialog, self).__init__(parent,-1,title, style = wx.CAPTION|wx.CLOSE_BOX|wx.TAB_TRAVERSAL)
		self.symbolsManager = symbolsManager
		self.basicCategoryNamesList = self.symbolsManager.getBasicCategoryNames()
		self.categoryNamesList = self.symbolsManager.getCategoryNames()
		self.curIndexInSymbolCategoryListBox = 0
		self.InitLists()
		self.doGui()
	
	def InitLists(self, index = 0):
		categoryName  = self.categoryNamesList[index]
		(symbolList, descriptionList) = self.symbolsManager.getSymbolAndDescriptionList(categoryName)
		self.complexSymbolsList= symbolList[:]
		self.symbolDescriptionList= descriptionList[:]
	
	def doGui(self):
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		# the category list box
		# Translators: This is a label appearing on complex symbols dialog.
		symbolCategoryListLabelText=_("&Categories:")
		if wx.version().startswith("4"):
			# for wxPython 4
			self.symbolCategoryListBox_ID = wx.NewIdRef()
		else:
			self.symbolCategoryListBox_ID = wx.NewId()
		self.symbolCategoryListBox =sHelper.addLabeledControl(symbolCategoryListLabelText, wx.ListBox,id = self.symbolCategoryListBox_ID,name= "CategoryNames" ,choices=self.categoryNamesList, style = wx.LB_SINGLE |wx.LB_ALWAYS_SB|wx.WANTS_CHARS,size= (948, 130))
		if self.symbolCategoryListBox.GetCount():
			self.symbolCategoryListBox.SetSelection(0)
		
		# the symbol list box
		# Translators: This is a label appearing on complex symbols dialog.
		symbolsListLabelText=_("S&ymbols:")
		self.symbolsListBox =sHelper.addLabeledControl(symbolsListLabelText, wx.ListBox,id = wx.ID_ANY,name= "symbols list" ,choices=self.symbolDescriptionList, style = wx.LB_SINGLE |wx.LB_ALWAYS_SB, size= (948,390))
		# Buttons
		# Buttons are in a horizontal row
		bHelper= guiHelper.ButtonHelper(wx.HORIZONTAL)
		# Translators: This is a label of a button appearing on complex symbols dialog.
		copyButton =  bHelper.addButton(self, label=_("&Copy to clipboard"))
		# Translators: This is a label of a button appearing on complex symbols dialog.
		pasteButton =  bHelper.addButton(self, label=_("&Past"))
		# Translators: This is a label of a button appearing on complex symbols dialog.
		pasteButton.SetDefault()
		# Translators: This is a label of a button appearing on complex symbols dialog.
		manageSymbolsButton =  bHelper.addButton(self, label=_("&Manage yours symbols"))
		sHelper.addItem(bHelper)
		bHelper = sHelper.addDialogDismissButtons(gui.guiHelper.ButtonHelper(wx.HORIZONTAL))
		closeButton= bHelper.addButton(self, id = wx.ID_CLOSE, label = NVDAString("&Close"))
		mainSizer.Add(sHelper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		mainSizer.Fit(self)
		self.SetSizer(mainSizer)
		# Events
		copyButton.Bind(wx.EVT_BUTTON,self.onCopyButton)
		pasteButton.Bind(wx.EVT_BUTTON,self.onPasteButton)
		manageSymbolsButton.Bind(wx.EVT_BUTTON,self.onManageSymbolsButton)
		closeButton.Bind(wx.EVT_BUTTON, lambda evt: self.Destroy())
		self.symbolCategoryListBox.Bind(wx.EVT_LISTBOX, self.onSelectCategory)
		self.symbolCategoryListBox.Bind(wx.EVT_KEY_DOWN, self.onKeydown)
		self.symbolsListBox.Bind(wx.EVT_KEY_DOWN, self.onKeydown)
		self.SetEscapeId(wx.ID_CLOSE)
	def Destroy(self):
		complexSymbolsDialog._instance = None
		super(complexSymbolsDialog, self).Destroy()
	
	def onSelectCategory(self,event):
		index = self.symbolCategoryListBox.GetSelection()
		self.curIndexInSymbolCategoryListBox = index
		if index>= 0:
			self.InitLists(index)
			# update symbolListBox
			self.symbolsListBox.Clear()
			self.symbolsListBox.AppendItems(self.symbolDescriptionList)

		event.Skip()
	
	def onKeydown(self, event):
		keyCode= event.GetKeyCode()
		if keyCode == wx.WXK_SPACE:
			index = self.symbolsListBox.GetSelection()

			if index == -1:
				return
			
			symbol = self.complexSymbolsList[index]
			c = ord(symbol)
			core.callLater(400,speech.speakMessage, "%d," % c)
			core.callLater(450, speech.speakSpelling,hex(c))
			return

		if keyCode == wx.WXK_TAB:
			shiftDown = event.ShiftDown()
			if shiftDown:
				wx.Window.Navigate(self.symbolCategoryListBox,wx.NavigationKeyEvent.IsBackward)
			else:
				wx.Window.Navigate(self.symbolCategoryListBox,wx.NavigationKeyEvent.IsForward)
			return

		id = event.GetId()
		if keyCode == wx.WXK_RETURN and id == self.symbolCategoryListBox_ID:
			wx.Window.Navigate(self.symbolCategoryListBox,wx.NavigationKeyEvent.IsForward)
			return
		
		event.Skip()
	
	def onPasteButton(self, event):
		index = self.symbolsListBox.GetSelection()
		if index == -1:
		# Translators: This is a message announced in complex symbols dialog.
			speakLater(300, _("No symbol selected"))
			return
		symbol = self.complexSymbolsList[index]
		symbolDescription = self.symbolsListBox.GetString(index)
		result= copyToClip(symbol)
		if result == False:
			c = ord(symbol)
			l= self.symbolDescriptionList[index]
			log.error("error copyToClip symbol:%s (%s)  code = %d" %(l, symbol,c))
		
		else:
			# Translators: This is a message announced  in complex symbols dialog.
			msg =_("{0} pasted").format(self.symbolDescriptionList[index])
			speech.speakMessage(msg)
			time.sleep(2.0)
			core.callLater( 200, SendKey, "Control+v")
		from ..settings import _addonConfigManager
		_addonConfigManager.updateLastSymbolsList( symbolDescription, symbol)
		self.Close()
	
	def onCopyButton(self, event):
		index = self.symbolsListBox.GetSelection()
		if index == -1:
		# Translators: This is a message announced   in complex symbols dialog.
			speakLater(300, _("No symbol selected"))
			return
		symbol = self.complexSymbolsList[index]
		symbolDescription = self.symbolsListBox.GetString(index)
		result = copyToClip(symbol)
		if result == False:
			c = ord(symbol)
			l= self.symbolDescriptionList[index]
			log.warning("error copyToClip symbol:%s (%s)  code = %d" %(l, symbol,c))
			# Translators: message to the user to report copy to clipboard error.
			msg = _("Symbol cannot copied to the clipboard")
		else:
			# Translators: This is a message announced  in complex symbols dialog.
			msg =_("{0} copied").format(self.symbolDescriptionList[index])
		speech.speakMessage(msg)
		time.sleep(2.0)
		from ..settings import _addonConfigManager
		_addonConfigManager .updateLastSymbolsList(symbolDescription, symbol)
		self.Close()

	
	def onManageSymbolsButton(self, evt):
		with    ManageSymbolsDialog(self) as d:
			d.ShowModal() 

			if d.noChange:
				return
			categoryName = self.symbolCategoryListBox.GetStringSelection()
			self.categoryNamesList = self.symbolsManager.getCategoryNames()
			self.symbolCategoryListBox.Clear()
			self.symbolCategoryListBox.AppendItems(self.categoryNamesList )
			index = 0
			if categoryName in self.categoryNamesList :
				index = self.categoryNamesList .index(categoryName)
			self.symbolCategoryListBox.SetSelection(index)
			self.onSelectCategory(evt)
			self.symbolCategoryListBox.SetFocus()				
	
	@classmethod
	def run(cls):
		if isOpened(cls):
			return
		symbolsManager = symbols.SymbolsManager()
		if not symbolsManager.isReady():
			if gui.messageBox(
				# Translators: the label of a message box dialog.
				_("Error: no basic symbols installed"),
				# Translators: the title of a message box dialog.
				_("Warning"),
				wx.OK|wx.ICON_WARNING):
				pass
			return
		gui.mainFrame.prePopup()		
		d =   cls(gui.mainFrame,symbolsManager)
		d.CentreOnScreen()
		d.Show()
		gui.mainFrame.postPopup()		


class ManageSymbolsDialog(wx.Dialog):
	shouldSuspendConfigProfileTriggers = True
	# Translators: This is the title of Manage Symbols Dialog window.
	title = _("User symbols manager")
	
	def __init__(self, parent):
		super(ManageSymbolsDialog, self).__init__(None,-1,title=self.title, style = wx.CAPTION|wx.CLOSE_BOX|wx.TAB_TRAVERSAL)
		self.noChange = True
		self.parent = parent
		self.symbolsManager = self.parent.symbolsManager
		self.userComplexSymbols = self.symbolsManager.getUserSymbolCategories()
		self.curCategoryIndex = parent.curIndexInSymbolCategoryListBox 
		self.categoryNamesList = parent.categoryNamesList
		self.InitLists(self.parent.symbolCategoryListBox.GetSelection())
		self.doGui()
		self.CentreOnScreen()
	
	def InitLists(self, index = 0):
		categoryName =self.categoryNamesList [index]
		(symbolList, descriptionList) = self.symbolsManager.getUserSymbolAndDescriptionList(categoryName, self.userComplexSymbols)
		self.symbolDescriptionList= descriptionList[:]
		self.complexSymbolsList= symbolList[:]
		
	def doGui(self):
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		# the category list box
		# Translators: This is a label appearing on Manage Symbols Dialog.
		symbolCategoryListLabelText=_("&Categories:")
		if wx.version().startswith("4"):
			# for wxPython 4
			self.symbolCategoryListBox_ID = wx.NewIdRef()
		else:
			# for wxPython 3
			self.symbolCategoryListBox_ID = wx.NewId()
		self.symbolCategoryListBox =sHelper.addLabeledControl(symbolCategoryListLabelText, wx.ListBox,id = self.symbolCategoryListBox_ID,name= "Categories" ,choices=self.categoryNamesList, style = wx.LB_SINGLE |wx.LB_ALWAYS_SB|wx.WANTS_CHARS,size= (948, 130))
		if self.symbolCategoryListBox.GetCount():
			self.symbolCategoryListBox.SetSelection(self.curCategoryIndex)
		
		# the symbol list box
		# Translators: This is a label appearing on Manage Symbols Dialog.
		symbolsListLabelText=_("S&ymbols:")
		self.symbolsListBox =sHelper.addLabeledControl(symbolsListLabelText, wx.ListBox,id = wx.ID_ANY,name= "symbols list" ,choices=self.symbolDescriptionList, style = wx.LB_SINGLE , size= (948,390))

		# first line of Buttons
		bHelper= guiHelper.ButtonHelper(wx.HORIZONTAL)
		# Translators: This is a label of a button appearing on Manage Symbols Dialog.
		addSymbolButton =  bHelper.addButton(self, label=_("&Add a symbol"))
		# Translators: This is a label of a button appearing on Manage Symbols Dialog.
		deleteSymbolButton =  bHelper.addButton(self, label=_("&Delete the symbol"))
		# Translators: This is a label of a button appearing on Manage Symbols Dialog.
		addCategoryButton =  bHelper.addButton(self, label=_("Add a &category"))
		# Translators: This is a label of a button appearing on Manage Symbols Dialog.
		self.deleteCategoryButton =  bHelper.addButton(self, label=_("De&lete the category"))
		sHelper.addItem(bHelper)
		#second line of buttons
		bHelper = sHelper.addDialogDismissButtons(gui.guiHelper.ButtonHelper(wx.HORIZONTAL))
		# Translators: This is a label of a button appearing on Manage Symbols Dialog.
		saveButton =  bHelper.addButton(self, label=_("&Save"))
		cancelButton= bHelper.addButton(self, id = wx.ID_CANCEL)
		mainSizer.Add(sHelper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		mainSizer.Fit(self)
		self.SetSizer(mainSizer)
		
		# Events
		addSymbolButton.Bind(wx.EVT_BUTTON,self.onAddSymbolButton)
		deleteSymbolButton.Bind(wx.EVT_BUTTON,self.onDeleteSymbolButton)
		addCategoryButton.Bind(wx.EVT_BUTTON,self.onAddCategoryButton)
		self.deleteCategoryButton.Bind(wx.EVT_BUTTON,self.onDeleteCategoryButton)
		saveButton.Bind(wx.EVT_BUTTON,self.onSaveButton)
		self.symbolCategoryListBox.Bind(wx.EVT_LISTBOX, self.onSelect)
		self.symbolCategoryListBox.Bind(wx.EVT_KEY_DOWN, self.onKeydown)
		self.symbolsListBox.Bind(wx.EVT_KEY_DOWN, self.onKeydown)
		self.SetEscapeId(wx.ID_CANCEL)
		self.updateButtons()
		
	def updateButtons(self):
		categoryName = self.symbolCategoryListBox.GetStringSelection()
		if categoryName  in self.parent.basicCategoryNamesList :
			self.deleteCategoryButton.Disable()
		else:
			self.deleteCategoryButton.Enable()

	
	def onSelect(self,event):
		index = self.symbolCategoryListBox.GetSelection()
		if index>= 0:
			self.InitLists(index)
			# update symbolListBox
			self.symbolsListBox.Clear()
			self.symbolsListBox.AppendItems(self.symbolDescriptionList)
		self.updateButtons()
		
		event.Skip()
	
	def onKeydown(self, evt):
		keyCode= evt.GetKeyCode()
		if keyCode == wx.WXK_SPACE:
			index = self.symbolsListBox.GetSelection()

			if index == -1:
				return
			
			symbol = self.complexSymbolsList[index]
			c = ord(symbol)
			core.callLater(400,speech.speakMessage, "%d," % c)
			core.callLater(450, speech.speakSpelling,hex(c))
			return

		if keyCode == wx.WXK_TAB:
			shiftDown = evt.ShiftDown()
			if shiftDown:
				wx.Window.Navigate(self.symbolCategoryListBox,wx.NavigationKeyEvent.IsBackward)
			else:
				wx.Window.Navigate(self.symbolCategoryListBox,wx.NavigationKeyEvent.IsForward)
			return

		id = evt.GetId()
		if keyCode == wx.WXK_RETURN and id == self.symbolCategoryListBox_ID:
			wx.Window.Navigate(self.symbolCategoryListBox,wx.NavigationKeyEvent.IsForward)
			return
		
		evt.Skip()
	
	def onDeleteSymbolButton(self, evt):
		index = self.symbolsListBox.GetSelection()
		if index == -1:
		# Translators: This is a message announced in  Manage Symbols Dialog.
			core.callLater(300,speech.speakMessage,_("No symbol selected"))
			return

		symbol = self.complexSymbolsList[index]
		description = self.symbolsListBox.GetStringSelection()
		categoryName = self.symbolCategoryListBox.GetStringSelection()
		del self.userComplexSymbols[categoryName][symbol]
		self.onSelect(evt)
		# Translators: This is a message announced in  Manage Symbols Dialog.
		core.callLater(300, speech.speakMessage,_("%s symbol deleted")%description)

		evt.Skip()
	
	def validateSymbol(self, categoryName,symbol, description):
		if len(symbol) == 0  and len(description) == 0:
			return False
		if len( symbol)== 0:
			# Translators: This is a message announced in  Manage Symbols Dialog.
			core.callLater(300, speech.speakMessage, _("No symbol entered"))
			return False
		if len(symbol)>1:
			# Translators: This is a message announced in  Manage Symbols Dialog.
			core.callLater(300, speech.speakMessage,_("Symbol is not valid"))
			return False
		if len(description) ==0:
			# Translators: This is a message announced in  Manage Symbols Dialog.
			core.callLater(300,speech.speakMessage ,_("There is no description for the symbol"))
			return False
		for cat in self.parent.categoryNamesList:
			(symbolList, descriptionList) = self.symbolsManager.getSymbolAndDescriptionList(cat)
			if symbol in symbolList:
				description = descriptionList[symbolList.index(symbol)]
				if cat == categoryName:
					if gui.messageBox(
						# Translators: the label of a message box dialog.
						_("""The symbol is allready in this category under "%s" description. Do you want to replace it ?"""%description),
						# Translators: the title of a message box dialog.
						_("Confirmation"),
						wx.YES|wx.NO|wx.ICON_WARNING)==wx.NO:
						return False
				else:
					if gui.messageBox(
						# Translators: the label of a message box dialog.
						_("The symbol is allready in {oldCat} category. Do you want to add this symbol also in {newCat} category?").format( oldCat = cat, newCat = categoryName),
						# Translators: the title of a message box dialog.
						_("Confirmation"),
						wx.YES|wx.NO|wx.ICON_WARNING)==wx.NO:
						return False
		
		return True
	def onAddSymbolButton(self, evt):
		categoryName = self.symbolCategoryListBox.GetStringSelection()
		with AddSymbolDialog(self, categoryName) as entryDialog:
			if entryDialog.ShowModal() != wx.ID_OK:
				return
			
			symbol = entryDialog.symbolEdit.GetValue()
			description = entryDialog.descriptionEdit.GetValue()
			if not self.validateSymbol(categoryName, symbol,description):
				return
			if categoryName not in self.userComplexSymbols:
				self.userComplexSymbols[categoryName] = {}
			
			self.userComplexSymbols[categoryName][symbol] = description
			self.onSelect(evt)
			# Translators: This is a message announced in  Manage Symbols Dialog.
			core.callLater(300, speech.speakMessage, _("%s symbol has been added")	 %description)
		
		evt.Skip()		
				
	def onAddCategoryButton(self, evt):
		with wx.TextEntryDialog(self, 
						# Translators: Message to show on the dialog.
			_("Entry category name:"),
			# Translators: This is a title  of text control  of dialog box in   Manage Symbols Dialog.
			_("Adding category"),
			"") as entryDialog:
			if entryDialog.ShowModal() != wx.ID_OK:
				return
			categoryName = entryDialog.Value
			if categoryName in self.userComplexSymbols or categoryName in self.categoryNamesList:
				# Translators: This is a message announced in   Manage Symbols Dialog.
				core.callLater(300,ui.message, _("%s category allready exists")%categoryName)
			else:
				self.userComplexSymbols[categoryName] = {}
				self.categoryNamesList.append(categoryName)
				self.symbolCategoryListBox.Clear()
				self.symbolCategoryListBox.AppendItems(self.categoryNamesList)
				self.symbolCategoryListBox.SetSelection(self.categoryNamesList.index(categoryName))
				self.onSelect(evt)
				
				
		evt.Skip()
	def onDeleteCategoryButton(self, evt):
		categoryName = self.symbolCategoryListBox.GetStringSelection()
		if categoryName  in self.parent.basicCategoryNamesList :
			# Translators: This is a message announced in Manage Symbols Dialog.
			core.callLater(300, speech.speakMessage ,_("You cannot delete this basic category."))
			return
		index = self.categoryNamesList.index(categoryName)
		if gui.messageBox(
			# Translators: the label of a message box dialog.
			_("Do you vwant realy delete this category and all its symbols ?"),
			# Translators: the title of a message box dialog.
			_("Confirmation"),
			wx.YES|wx.NO|wx.ICON_WARNING)==wx.NO:
			return

		if index == len(self.categoryNamesList) -1:
			index = index-1 if index else index
		del self.userComplexSymbols[categoryName]
		self.categoryNamesList.remove(categoryName)
		self.symbolCategoryListBox.Clear()
		self.symbolCategoryListBox.AppendItems(self.categoryNamesList)
		self.symbolCategoryListBox.SetSelection(index)
			# Translators: This is a message announced in Manage Symbols Dialog.
		core.callLater(300, speech.speakMessage,_("%s category has been deleted")%categoryName)
		self.onSelect(evt)
		evt.Skip()

		
	def onSaveButton(self, evt):
		self.symbolsManager.saveUserSymbolCategories(self.userComplexSymbols)
		self.noChange = False
		self.Close()

class AddSymbolDialog(wx.Dialog):
	shouldSuspendConfigProfileTriggers = True
	# Translators: This is the title  of  the add symbol dialog.
	title = _("Adding Symbol in %s category")
	
	def __init__(self, parent,categoryName):
		super(AddSymbolDialog,self).__init__(parent, title=self.title %categoryName)
		mainSizer=wx.BoxSizer(wx.VERTICAL)
		sHelper = gui.guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		# Translators: This is the label of the edit field appearing in the add symbol dialog.
		symbolEditLabelText = _("Enter the Symbol:")
		self.symbolEdit = sHelper.addLabeledControl(symbolEditLabelText, wx.TextCtrl)
		# Translators: This is the label of symbol description edit field appearing in in the add symbol dialog.
		descriptionEditLabelText = _("Enter the Description:")
		self.descriptionEdit  = sHelper.addLabeledControl(descriptionEditLabelText , wx.TextCtrl)
		sHelper.addDialogDismissButtons(self.CreateButtonSizer(wx.OK|wx.CANCEL))
		mainSizer.Add(sHelper.sizer, border=gui.guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		mainSizer.Fit(self)
		self.SetSizer(mainSizer)
		self.symbolEdit.SetFocus()
		self.CentreOnScreen()

class LastUsedComplexSymbolsDialog(wx.Dialog):
	shouldSuspendConfigProfileTriggers = True
	_instance = None
	title = None

	
	def __new__(cls, *args, **kwargs):
		if LastUsedComplexSymbolsDialog._instance is not None:
			return LastUsedComplexSymbolsDialog._instance
		return wx.Dialog.__new__(cls)
	
	def __init__(self, parent, lastUsedSymbols):
		if LastUsedComplexSymbolsDialog._instance is not None:
			return
		LastUsedComplexSymbolsDialog._instance = self
		profileName = config.conf.profiles[-1].name
		if profileName is None:
			profileName = NVDAString("normal configuration")
		# Translators: This is the title of Last Used Complex Symbols Dialog.
		dialogTitle = _("Last used complex symbols")
		dialogTitle = "%s (%s)" %(dialogTitle, profileName)
		title = LastUsedComplexSymbolsDialog.title = makeAddonWindowTitle(dialogTitle)
		super(LastUsedComplexSymbolsDialog, self).__init__(parent,-1,title, style = wx.CAPTION|wx.CLOSE_BOX|wx.TAB_TRAVERSAL)
		self.lastUsedSymbols = lastUsedSymbols
		self.doGui()


		
	
	def doGui(self):
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		# the last used symbols list
		# Translators: This is a label appearing on Last used complex symbols dialog.
		symbolsListLabelText=_("&Symbols:")
		if wx.version().startswith("4"):
			# for wxpython 4
			self.symbolsListBox_ID = wx.NewIdRef()
		else:
			# for wxPython 3
			self.symbolsListBox_ID = wx.NewId()
		self.symbolsListBox =sHelper.addLabeledControl(symbolsListLabelText, wx.ListBox,id = self.symbolsListBox_ID,name= "Symbols" ,choices=[desc for (desc, symbol) in self.lastUsedSymbols], style = wx.LB_SINGLE |wx.LB_ALWAYS_SB,size= (948, 130))
		if self.symbolsListBox.GetCount():
			self.symbolsListBox.SetSelection(0)
		
		# Buttons
		# Buttons are in a horizontal row
		bHelper= guiHelper.ButtonHelper(wx.HORIZONTAL)
		# Translators: This is a label of a button appearing on Last Used Complex Symbols Dialog.
		copyButton =  bHelper.addButton(self, label=_("&Copy to clipboard"))
		# Translators: This is a label of a button appearing on Last Used Complex Symbols Dialog.
		pasteButton =  bHelper.addButton(self,label=_("&Past"))
		pasteButton.SetDefault()
		# Translators: This is a label of a button appearing on last Used Symbols dialog.
		cleanButton =  bHelper.addButton(self,label=_("&Delete all"))
		sHelper.addItem(bHelper)
		bHelper = sHelper.addDialogDismissButtons(gui.guiHelper.ButtonHelper(wx.HORIZONTAL))
		closeButton= bHelper.addButton(self, id = wx.ID_CLOSE, label = NVDAString("&Close"))
		mainSizer.Add(sHelper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		mainSizer.Fit(self)
		self.SetSizer(mainSizer)
		# Events
		copyButton.Bind(wx.EVT_BUTTON,self.onCopyButton)
		pasteButton.Bind(wx.EVT_BUTTON,self.onPasteButton)
		cleanButton.Bind(wx.EVT_BUTTON,self.onCleanButton)
		closeButton.Bind(wx.EVT_BUTTON, lambda evt: self.Destroy())
		self.SetEscapeId(wx.ID_CLOSE)
	
	def Destroy(self):
		LastUsedComplexSymbolsDialog._instance = None
		super(LastUsedComplexSymbolsDialog, self).Destroy()
	
	def onPasteButton(self, event):
		index = self.symbolsListBox.GetSelection()
		if index == -1:
		# Translators: This is a message announced in Last Used Complex Symbols Dialog.
			speakLater(300, _("No symbol selected"))
			return
		(description, symbol) = self.lastUsedSymbols[index]
		result= copyToClip(symbol)
		if result == False:
			c = ord(symbol)
			log.error("error copyToClip symbol:%s (%s)  code = %d" %(description, symbol,c))
		else:
			# Translators: This is a message announced  in complex symbols dialog.
			msg =_("{0} pasted").format(description)
			speech.speakMessage(msg)
			time.sleep(2.0)
			core.callLater( 200, SendKey, "Control+v")
	
		self.Close()
	
	def onCopyButton(self, event):
		index = self.symbolsListBox.GetSelection()
		if index == -1:
			# Translators: This is a message announced   in Last Used Complex Symbols Dialog.
			speakLater(300, _("No symbol selected"))
			return
		(description,symbol) = self.lastUsedSymbols[index]
		result = copyToClip(symbol)
		if result == False:
			c = ord(symbol)
			log.error("error copyToClip symbol:%s (%s)  code = %d" %(description, symbol,c))
		else:
			# Translators: This is a message announced  in Last Used Complex Symbols Dialog.
			text =_("{0} copied").format(description)
			speech.speakMessage(text)
			time.sleep(2.0)
		self.Close()
	
	def onCleanButton(self, event):
		if gui.messageBox(
			# Translators: the label of a message box dialog.
			_("Do you want really delete all symbols of the list"),
			# Translators: the title of a message box dialog.
			_("Confirmation"),
			wx.YES|wx.NO) == wx.YES:
			from ..settings import _addonConfigManager
			_addonConfigManager.cleanLastUsedSymbolsList()
		self.Close()
	
	@classmethod
	def run(cls):
		if isOpened(cls):
			return
		from ..settings import _addonConfigManager
		lastUsedSymbols = _addonConfigManager.getLastUsedSymbols()
		if len(lastUsedSymbols) == 0:
			# Translators: message to the user when there is no used symbol recorded.
			speech.speakMessage(_("There is no symbol recorded"))
			return
		gui.mainFrame.prePopup()
		d =   cls(gui.mainFrame, lastUsedSymbols)
		d.CentreOnScreen()
		d.Show()
		gui.mainFrame.postPopup()

