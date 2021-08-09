# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from instana.w3c_trace_context.tracestate import Tracestate
import unittest


class TestTracestate(unittest.TestCase):
    def setUp(self):
        self.ts = Tracestate()

    def test_get_instana_ancestor(self):
        tracestate = "congo=t61rcWkgMzE,in=1234d0e0e4736234;1234567890abcdef"
        ia = self.ts.get_instana_ancestor(tracestate)
        self.assertEqual(ia.t, "1234d0e0e4736234")
        self.assertEqual(ia.p, "1234567890abcdef")

    def test_get_instana_ancestor_no_in(self):
        tracestate = "congo=t61rcWkgMzE"
        self.assertIsNone(self.ts.get_instana_ancestor(tracestate))

    def test_get_instana_ancestor_tracestate_None(self):
        tracestate = None
        self.assertIsNone(self.ts.get_instana_ancestor(tracestate))

    def test_update_tracestate(self):
        tracestate = "congo=t61rcWkgMzE"
        in_trace_id = "1234d0e0e4736234"
        in_span_id = "1234567890abcdef"
        expected_tracestate = "in=1234d0e0e4736234;1234567890abcdef,congo=t61rcWkgMzE"
        self.assertEqual(expected_tracestate, self.ts.update_tracestate(tracestate, in_trace_id, in_span_id))

    def test_update_tracestate_None(self):
        tracestate = None
        in_trace_id = "1234d0e0e4736234"
        in_span_id = "1234567890abcdef"
        expected_tracestate = "in=1234d0e0e4736234;1234567890abcdef"
        self.assertEqual(expected_tracestate, self.ts.update_tracestate(tracestate, in_trace_id, in_span_id))

    def test_update_tracestate_more_than_32_members_already(self):
        tracestate = "congo=t61rcWkgMzE,robo=1221213jdfjkdsfjsd,alpha=5889fnjkllllllll," \
                     "beta=aslsdklkljfdshasfaskkfnnnsdsd,gamadeltaepsilonpirpsigma=125646845613675451535445155126666fgsdfdsfjsdfhsdfsdsdsaddfasfdfdsfdsfsd;qwertyuiopasdfghjklzxcvbnm1234567890," \
                     "b=121,c=23344,d=asd,e=ldkfj,f=1212121,g=sadahsda,h=jjhdada,i=eerjrjrr,j=sadsasd,k=44444,l=dadadad," \
                     "m=rrrr,n=3424jdg,p=ffss,q=12,r=3,s=5,t=u5,u=43,v=gj,w=wew,x=23123,y=sdf,z=kasdl,aa=dsdas,ab=res," \
                     "ac=trwa,ad=kll,ae=pds"
        in_trace_id = "1234d0e0e4736234"
        in_span_id = "1234567890abcdef"
        expected_tracestate = "in=1234d0e0e4736234;1234567890abcdef,congo=t61rcWkgMzE,robo=1221213jdfjkdsfjsd," \
                              "alpha=5889fnjkllllllll,beta=aslsdklkljfdshasfaskkfnnnsdsd,b=121,c=23344,d=asd,e=ldkfj," \
                              "f=1212121,g=sadahsda,h=jjhdada,i=eerjrjrr,j=sadsasd,k=44444,l=dadadad,m=rrrr,n=3424jdg," \
                              "p=ffss,q=12,r=3,s=5,t=u5,u=43,v=gj,w=wew,x=23123,y=sdf,z=kasdl,aa=dsdas,ab=res,ac=trwa"
        actual_tracestate = self.ts.update_tracestate(tracestate, in_trace_id, in_span_id)
        self.assertEqual(len(tracestate.split(",")), 34)  # input had 34 list members
        self.assertEqual(len(actual_tracestate.split(",")), 32)  # output has 32 list members, 3 removed and 1 added
        self.assertEqual(expected_tracestate, actual_tracestate)
        self.assertNotIn("gamadeltaepsilonpirpsigma",
                         actual_tracestate)  # member longer than 128 characters gets removed

    def test_update_tracestate_empty_string(self):
        tracestate = ""
        in_trace_id = "1234d0e0e4736234"
        in_span_id = "1234567890abcdef"
        expected_tracestate = "in=1234d0e0e4736234;1234567890abcdef"
        self.assertEqual(expected_tracestate, self.ts.update_tracestate(tracestate, in_trace_id, in_span_id))

    def test_update_tracestate_exception(self):
        tracestate = []
        in_trace_id = "1234d0e0e4736234"
        in_span_id = "1234567890abcdef"
        expected_tracestate = []
        self.assertEqual(expected_tracestate, self.ts.update_tracestate(tracestate, in_trace_id, in_span_id))