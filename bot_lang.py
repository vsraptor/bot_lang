#!/usr/bin/python
from lark import Lark, Token, Tree
from lark import Transformer
import random
import os
import glob
import hiyapyco
#import logging as log


class AttrDict(dict):
	def __init__(self, *args, **kwargs):
		super(AttrDict, self).__init__(*args, **kwargs)
		self.__dict__ = self


#add text at the begining of every line
def prepend(txt, what):
	res = ''
	for line in txt.splitlines() : res += what + line + "\n"
	return res

class KV(tuple): pass

class KVS(list):
	def render(self, fmt=None, indent=''):
		lst = []
		for kv in self :
			if isinstance(kv,KV) :
				lst.append("%s: %s" % ( kv[0], kv[1]))

		kvstr = '{' + ', '.join(lst) + '}'
		if fmt == 'utter' : return "- " + kvstr
		return kvstr

#============================================================================================

class BotTransformer(Transformer, object):

	def __init__(self) :
		super(self.__class__,self).__init__()
		self.data = AttrDict({
			'domain' : AttrDict({
				'slots': [], 'entities': [],'actions': [], 'utters': [], 'intents': [], 'forms' : []
			}),
			'intents': AttrDict({}), 'stories': AttrDict({}),'utters': AttrDict({}),
		})

#------------ STORY --------------------------------------------

	def story(self, items):
		rv = "## %s\n%s\n" % (items[1],items[2])
		self.data.stories[items[1]] = rv
		return items

	def pairs(self, items):
		return self.join(items, suffix="\n")

	def pair(self, items):
		return self.join(items, suffix="\n", indent='  ')

	def heads(self, items):
		if len(items) > 0  : items = " OR ".join(items)
		return self.join([items], prefix='* ',suffix="\n")

	def head(self, items):
		rv = items[0]
		if len(items) > 1 and isinstance(items[1], KVS) : rv += items[1].render()
		return rv

	def body(self, items):
		return self.join(items, prefix='- ', suffix="\n", indent='  ')

	def sitem(self, items):
		rv = items[0]
		if len(items) > 1 and isinstance(items[1], KVS) : rv += items[1].render()
		return rv

	#generate utter_* from String
	def story_utter(self, (utter,)):
		utter_name = "utter_" + str(random.randint(1000,9999))
		txt = utter if utter[0] == '"' else "\"%s\"" % utter
		self.data.utters[utter_name] = "%s:\n  - text: %s" % (utter_name, txt)
		self.data.domain.utters.append(utter_name)
		self.data.domain.actions.append(utter_name)

		return utter_name



#------------ INTENT --------------------------------------------


	def intent(self, items):
		rv = "## intent:%s\n%s\n" % (items[1],items[2])
		self.data.intents[items[1]] = rv
		self.data.domain.intents.append(items[1])
		return rv

	def ilist(self, items):
		return self.join(items, prefix='- ', suffix="\n")

#------------ UTTER --------------------------------------------

	def utter(self, items):
		rv = "utter_%s:\n%s" % (items[1],items[2])
		self.data.utters[items[1]] = rv
		self.data.domain.actions.append('utter_' + items[1])
		self.data.domain.utters.append('utter_' + items[1])
		return rv

	def ulist(self, items):
		return self.join(items, suffix="\n", indent='  ')

	def uitem(self, items):
		rv = ''
		if isinstance(items[0], KVS) : rv = items[0].render(fmt='utter', indent='  ')
		else : rv = '- text: ' + items[0].strip()

		return rv

#------------ KVS --------------------------------------------

	def kvs(self, items): return KVS(items)

	def kv(self, items):
		key, val = items[0], items[1]
		return KV((key,val))

#------------ DOMAIN --------------------------------------------

	def domain(self, items):
		for i in items[1:] :
			if not isinstance(i, (Token,Tree)) : self.data.domain[items[0]].append(i)
	#			return items

	def domain_kws(self, items): return items[0]

	def slots(self, items):
		for i in items : self.data.domain.slots.append(i)

	def slot(self, items):
		return "%s : %s" % (items[0], items[1].render())


#------------BASIC --------------------------------------------

	def join(self, items, prefix='', suffix='', quote=False, indent='', ident_first=False):
		rv = indent if ident_first else ''
		for i in items :
			if not isinstance(i, (Tree,Token)) :
				istr = "\"%s\"" % i.strip() if quote else i.strip()
				rv += "%s%s%s%s" % (indent,prefix,istr,suffix)
		return rv

	def awords(self, items):
		return self.join(items,indent=' ')

	def ano(self, items): return ''.join(items)

	def text(self, (t,)) : return str(t)

	def string(self, (s,)): return str(s)

	def word(self, (t,)): return str(t)

	def number(self, (n,)):
		if n.isdigit() : return int(n)
		return float(n)


##============================= BOT Lang =================================
class BotLang(object):

	def test(self, txt, start='start'):
		self.parser = Lark(self.grammar(), start=start)
		self.tf = BotTransformer()
		self.tf.transform(self.parser.parse(txt))

	def dump(self):
		for k, usi in self.tf.data.items() :
			for item in usi.values() :
				if len(item) > 0 : print item


	def __init__(self):
		self.parser = Lark(self.grammar(), start='start')
		self.reset()

	def reset(self):
		self.tf = BotTransformer()

	#given file name read the file into string
	def file2str(self, fname):
		txt = ''
		with open(fname,'r') as f : txt = f.read()
		return txt

	def parse(self, fname):
		parsed = self.parser.parse(self.file2str(fname))
		txt = self.tf.transform(parsed)
		return txt


	def domain_write(self, fhandle, key):
		if len(self.tf.data.domain[key]) > 0 :
			fhandle.write("%s:\n" % key)
			data = self.tf.join( self.tf.data.domain[key], prefix='- ', suffix="\n", indent='  ')
			fhandle.write(data)


	#after the TF data is populated call this to generate the files
	def gen_files(self, prefix, path=''):
		print ">> Generate RASA files ..."
		nlu_md = path + prefix+"-nlu.md"
		print "  > %s" % nlu_md
		nlu = open(nlu_md, 'w')
		for intent in self.tf.data.intents.values() : nlu.write(intent)
		nlu.close()

		story_md = path + prefix+"-stories.md"
		print "  > %s" % story_md
		s = open(story_md, 'w')
		for story in self.tf.data.stories.values() : s.write(story)
		s.close()

		#returned back to the caller, for merging!?
		gen_yaml = path + prefix+"-domain.yml"
		print "  > %s" % gen_yaml
		doms = open(gen_yaml, 'w')

		#save the domain sections
		for key in ['intents', 'actions', 'entities', 'forms','slots'] :
			self.domain_write(doms, key)

		if len(self.tf.data.utters) > 0 :
			doms.write("templates:\n")
			for utter in self.tf.data.utters.values() : doms.write(prepend(utter, '  '))

		doms.close()
		return gen_yaml


	def grammar(self):
		return """

			?start : def+

			?def : domain | intent | utter | story | slots | _comments

			story: story_kw story_name _HB_SEP pairs _STMT_SEP
				?story_kw : "story"
				?story_name : word
				pairs : pair (_SPAIR_SEP pair)*
					pair : heads _PAIR_SEP body
				heads : head ("|" head)*
					head : sitem kvs?
				body : sitem (_SEP sitem)*
					sitem : word kvs? | story_utter
					story_utter : string

			intent : intent_kw intent_name _HB_SEP ilist _STMT_SEP
				?intent_kw : "intent"
				?intent_name : word
				ilist : iitem (_SEP iitem)*
					?iitem : awords | string

			utter : utter_kw utter_name _HB_SEP ulist _STMT_SEP
				?utter_name : word
				?utter_kw : "utter" | "say"
				ulist : uitem (_SEP uitem)*
					uitem : string | kvs | awords

			domain : domain_kws _HB_SEP word (_SEP word)* _STMT_SEP
				!domain_kws : "entities" | "actions" | "forms" | "intents"

				slots : "slots" _HB_SEP slot (_SEP slot)* _STMT_SEP
					slot : word kvs

			kvs : "{" kv (_SEP kv)* "}"
			kv : key ":" value
			?value : number | word | string
			?key : word | string


			_SPAIR_SEP : ">>"
			_HB_SEP : ":"
			_STMT_SEP : ";"
			_SEP : ","
			_PAIR_SEP : ">"
			_comments: /@.*/
			awords : aword+
			?aword : ano | word
			ano : OPEN word CLOSE
			word : /[\-\.A-Za-z0-9_]+/ | /[?!]/
			OPEN : /[\{\(\[]/
			CLOSE : /[\}\)\]]/
			text : /[A-Za-z0-9_ ]+/
			string : STRING
			number : NUMBER

			%import common.ESCAPED_STRING   -> STRING
			%import common.SIGNED_NUMBER    -> NUMBER
			%import common.WS
			%ignore WS

		"""

##=========================== COMPILER =========================================================
class BotLangCompiler(object):

	def __init__(self):
		self.bl = BotLang()

	def preprocess(self, ifile, ofile):
		print ">> Preprocess : %s => %s" % (ifile,ofile)
		os.system("cpp -P %s > %s" % (ifile,ofile))

	def merge_yaml(self, out_file, generated_yaml, yaml_path, yaml_mask='*.yml'):
		print ">> Merge yaml files : gen:%s + inp:%s/%s => %s" % (generated_yaml, yaml_path, yaml_mask, out_file)
		yaml_list = []

		for fname in glob.glob(os.path.join(yaml_path, yaml_mask)):
			with open(fname) as fp:
				yaml_file = fp.read()
				yaml_list.append(yaml_file)

			yaml_list.append(generated_yaml)
			merged_yaml = hiyapyco.load(yaml_list, method=hiyapyco.METHOD_MERGE)
			#print(hiyapyco.dump(merged_yaml))
			domain = open(out_file,"w+")
			domain.writelines(hiyapyco.dump(merged_yaml))


	def process(self, in_fname, out_prefix, out_path="./", pp=True, pp_cleanup=True, in_yaml=None, out_yaml=None):

		print ">> Process file:%s ..." % in_fname
		self.bl.reset()

		ifile = in_fname
		if pp : #pre process
			ppfile = "pp%s.out" % random.randint(1000,9999)
			self.preprocess(in_fname, ppfile)
			in_fname = ppfile

		self.bl.parse(in_fname)
		if out_path[-1] != '/' : out_path += '/'
		gen_yaml = self.bl.gen_files(prefix=out_prefix, path=out_path)

		if pp and pp_cleanup : os.remove(in_fname)

		#handle YAML
		if in_yaml is not None and out_yaml is not None :
			path, filename = os.path.split(in_yaml)
			self.merge_yaml(out_yaml, gen_yaml, yaml_path=path, yaml_mask=filename)




#========================================  MAIN  ====================================================================

# Example calls :
# c = BotLangCompiler()
#               src         ==>   dst
# c.process("./prj/base.inc", out_prefix='base', out_path='./data')
#               src         ==>   dst                              generated_yaml+in_yaml    ==>  final.yml
# c.process("./prj/test.inc", out_prefix='test', out_path='./tmp', in_yaml='./domain.yml', out_yaml='./tmp/final.yml')
#
#  Just merge yaml files :
#                        dst                         <===  generated  + yaml-files
# c.merge_yaml(out_file='./tmp/merge.yml', generated_yaml='./prj/test-domain.yml', yaml_path='./', yaml_mask='d*.yml')


if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser(description="""
		Bot language parser & generator for RASA chatbot ...\
		Ex.: bot_lang.py --in-file=./prj/test.inc --out-prefix=abc --out-path=./data --in-yaml=./prj/domain-exercise.yml --out-yaml=./data/final.yaml
	""")
	parser.add_argument('--in-file', help='input filename', required=True, dest='in_fname')
	parser.add_argument('--out-prefix', help='Prefix that is prepended on the output files', required=True, dest='out_prefix')
	parser.add_argument('--out-path', help='destination path', default='./', dest='out_path')
	parser.add_argument('--pp', help='Preprocess ...', type=bool, default=True, dest='pp')
	parser.add_argument('--pp-cleanup', help='showld it clean tmp preprocess file', type=bool, default=True, dest='pp_cleanup')
	parser.add_argument('--in-yaml', help='/path/*.yml : mask of which YAML files to merge with the generated YAML', dest='in_yaml')
	parser.add_argument('--out-yaml', help='/path/fname.yml : final merged YAML file', dest='out_yaml')
	args = parser.parse_args()

	compiler = BotLangCompiler()
	compiler.process(**vars(args))

