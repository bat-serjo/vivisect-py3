import unittest

import visgraph.graphcore as v_graphcore

s1paths = [
    ('a', 'c', 'f'),
    ('a', 'b', 'd', 'f'),
    ('a', 'b', 'e', 'f'),
]
s2paths = [
    ('a', 'b'),
    ('a', 'b', 'c'),
]


class GraphCoreTest(unittest.TestCase):
    def getSampleGraph1(self):
        # simple branching/merging graph
        g = v_graphcore.HierGraph()

        g.addHierRootNode('a')
        for c in ('b', 'c', 'd', 'e', 'f'):
            g.addNode(c)

        g.addEdgeByNids('a', 'b')
        g.addEdgeByNids('a', 'c')
        g.addEdgeByNids('c', 'f')
        g.addEdgeByNids('b', 'd')
        g.addEdgeByNids('b', 'e')
        g.addEdgeByNids('d', 'f')
        g.addEdgeByNids('e', 'f')

        return g

    def getSampleGraph2(self):
        # primitive loop graph
        g = v_graphcore.HierGraph()

        g.addHierRootNode('a')
        for c in ('b', 'c'):
            g.addNode(c)

        g.addEdgeByNids('a', 'b')
        g.addEdgeByNids('b', 'b')
        g.addEdgeByNids('b', 'c')

        return g

    def getSampleGraph3(self):
        # flat loop graph
        g = v_graphcore.HierGraph()

        g.addHierRootNode('a')
        for c in ('b', 'c', 'd'):
            g.addNode(c)

        g.addEdgeByNids('a', 'b')
        g.addEdgeByNids('b', 'c')
        g.addEdgeByNids('c', 'b')
        g.addEdgeByNids('c', 'd')

        return g

    def test_visgraph_pathscount(self):
        g = self.getSampleGraph1()
        self.assertEqual(g.getHierPathCount(), 3)

        g = self.getSampleGraph2()
        self.assertEqual(g.getHierPathCount(), 1)

        g = self.getSampleGraph3()
        self.assertEqual(g.getHierPathCount(), 1)

    def assertPathsFrom(self, g, paths):
        allpaths = set(paths)
        root = g.getNode('a')
        for path in g.getHierPathsFrom(root):
            nids = tuple([n[0] for (n, e) in path])
            self.assertIn(nids, allpaths)
            allpaths.remove(nids)
        self.assertFalse(allpaths)

    def test_visgraph_pathsfrom(self):
        self.assertPathsFrom(self.getSampleGraph1(), s1paths)
        self.assertPathsFrom(self.getSampleGraph2(), s2paths)

    def assertPathsTo(self, g, nid, paths):
        allpaths = set(paths)
        node = g.getNode(nid)
        for path in g.getHierPathsTo(node):
            nids = tuple([n[0] for (n, e) in path])
            self.assertIn(nids, allpaths)
            allpaths.remove(nids)
        self.assertFalse(allpaths)

    def test_visgraph_pathsto(self):
        """
        """
        self.assertPathsTo(self.getSampleGraph1(), 'f', s1paths)
        self.assertPathsTo(self.getSampleGraph2(), 'c', [('a', 'b', 'c'), ])

    def assertPathsThru(self, g, nid, paths):
        allpaths = set(paths)
        node = g.getNode(nid)
        for path in g.getHierPathsThru(node):
            nids = tuple([n[0] for (n, e) in path])
            self.assertIn(nids, allpaths)
            allpaths.remove(nids)
        self.assertFalse(allpaths)

    def test_visgraph_paththru(self):
        self.assertPathsThru(self.getSampleGraph1(), 'b', [('a', 'b', 'd', 'f'), ('a', 'b', 'e', 'f')])
        self.assertPathsThru(self.getSampleGraph2(), 'b', [('a', 'b'), ('a', 'b', 'c'), ])

    def test_visgraph_nodeprops(self):
        g = v_graphcore.Graph()
        a = g.addNode('a')

        g.setNodeProp(a, 'foo', 'bar')

        self.assertEqual(a[1].get('foo'), 'bar')

        self.assertTrue(a in g.getNodesByProp('foo'))
        self.assertTrue(a in g.getNodesByProp('foo', 'bar'))
        self.assertFalse(a in g.getNodesByProp('foo', 'blah'))

        g.delNodeProp(a, 'foo')

        self.assertFalse(a in g.getNodesByProp('foo'))
        self.assertFalse(a in g.getNodesByProp('foo', 'bar'))
        self.assertIsNone(a[1].get('foo'))

    def test_visgraph_edgeprops(self):
        g = v_graphcore.Graph()
        a = g.addNode('a')
        b = g.addNode('b')

        e = g.addEdge(a, b)
        g.setEdgeProp(e, 'foo', 'bar')

        self.assertEqual(e[3].get('foo'), 'bar')

        self.assertTrue(e in g.getEdgesByProp('foo'))
        self.assertTrue(e in g.getEdgesByProp('foo', 'bar'))
        self.assertFalse(e in g.getEdgesByProp('foo', 'blah'))

        g.delEdgeProp(e, 'foo')
        self.assertFalse(e in g.getEdgesByProp('foo'))
        self.assertFalse(e in g.getEdgesByProp('foo', 'bar'))
        self.assertIsNone(e[3].get('foo'))

    def test_visgraph_subcluster(self):

        g = v_graphcore.Graph()

        a = g.addNode('a')
        b = g.addNode('b')
        c = g.addNode('c')

        d = g.addNode('d')
        e = g.addNode('e')
        r = g.addNode('f')

        g.addEdgeByNids('a', 'b')
        g.addEdgeByNids('a', 'c')

        g.addEdgeByNids('d', 'e')
        g.addEdgeByNids('d', 'f')

        subs = g.getClusterGraphs()

        self.assertEqual(len(subs), 2)

        subtests = [{'a', 'b', 'c'}, {'d', 'e', 'f'}]

        for sub in subs:
            if sub.getNode('a'):
                self.assertIsNone(sub.getNode('d'))
                self.assertIsNone(sub.getNode('e'))
                self.assertIsNone(sub.getNode('f'))

                akids = [edge[2] for edge in sub.getRefsFromByNid('a')]

                self.assertTrue('b' in akids)
                self.assertTrue('c' in akids)

            elif sub.getNode('d'):
                self.assertIsNone(sub.getNode('a'))
                self.assertIsNone(sub.getNode('b'))
                self.assertIsNone(sub.getNode('c'))

                dkids = [edge[2] for edge in sub.getRefsFromByNid('d')]

                self.assertTrue('e' in dkids)
                self.assertTrue('f' in dkids)

            else:
                raise Exception('Invalid SubCluster!')

    def test_visgraph_formnode(self):
        g = v_graphcore.Graph()

        def wootctor(n):
            g.setNodeProp(n, 'lul', 1)

        n1 = g.formNode('woot', 10, ctor=wootctor)
        self.assertEqual(n1[1].get('lul'), 1)

        g.setNodeProp(n1, 'lul', 2)
        g.setNodeProp(n1, 'foo', 'bar')

        n2 = g.formNode('woot', 20, ctor=wootctor)
        n3 = g.formNode('woot', 10, ctor=wootctor)

        self.assertEqual(n1[0], n3[0])
        self.assertEqual(n1[1].get('lul'), 2)
        self.assertEqual(n3[1].get('foo'), 'bar')
        self.assertNotEqual(n1[0], n2[0])
