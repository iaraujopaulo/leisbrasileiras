from pathlib import Path
import sys, unittest
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent))
from integridade_anexos_decreto import anexo_proprio_ausente as gate

P=SimpleNamespace(visual=[],structure=[])
MAIN='DECRETO Nº 52.677\n\nArtigo único. Fica aprovado o Regimento que com êste baixa.\n\nBrasília, 14 de outubro de 1963; 142º da Independência.\n\nJOÃO GOULART\n\nPaulo de Tarso'
class Anexos(unittest.TestCase):
 def test_somente_assinaturas_ou_nota_retem(self):
  self.assertIsNotNone(gate(MAIN,P))
  self.assertIsNotNone(gate(MAIN+'\n\nO Regimento foi publicado no Diário Oficial de 17 de outubro.',P))
 def test_regimento_presente_nao_retem(self):
  self.assertIsNone(gate(MAIN+'\n\nREGIMENTO DA FACULDADE\n\nArt. 1º A Faculdade...',P))
 def test_citacao_de_outro_decreto_nao_retem(self):
  self.assertIsNone(gate(MAIN.replace('que com êste baixa','anexo ao Decreto nº 1.234 de 1960'),P))
 def test_link_tabela_ou_visual_exige_outra_analise(self):
  self.assertIsNotNone(gate(MAIN+'\n\n[Regimento](https://official/anexo)',P))
  self.assertIsNotNone(gate(MAIN+'\n\n<a href="anexo.pdf">ANEXO</a>',P))
  self.assertIsNotNone(gate(MAIN+'\n\nANEXO',P))
  self.assertIsNone(gate(MAIN+'\n\n[ANEXO](#anexo)\n\nANEXO\n\nArt. 1º Ficam fixados os valores.',P))
  self.assertIsNone(gate(MAIN,SimpleNamespace(visual=[],structure=[('table',())])))
  self.assertIsNone(gate(MAIN,SimpleNamespace(visual=['img'],structure=[])))
if __name__=='__main__':unittest.main()
