"""
A reverse engineering graph layout ...
"""

import enum
from collections import defaultdict

from vivisect import codegraph
import visgraph.layouts as vg_layout
import visgraph.drawing.bezier as vg_bezier

zero_zero = (0, 0)


def revenumerate(l):
    return zip(range(len(l) - 1, -1, -1), reversed(l))


SCOOCH_LEFT = 0
SCOOCH_RIGHT = 1


def adjustGraphLayout(graph: codegraph.CodeBlockGraph, node: int, col: int, row: int):
    nid, nprop = graph.getNode(node)

    nprop['col'] += col
    nprop['row'] += row

    edges = graph.getRefsFromByNid(node)
    for edge in edges:
        eid, from_node, to_node, eprop = edge
        adjustGraphLayout(graph, to_node, col, row)


class GraphLayoutType(enum.IntEnum):
    Wide = 0
    Medium = 1
    Narrow = 2


layout = GraphLayoutType.Narrow


def computeGraphLayout(graph: codegraph.CodeBlockGraph, node):
    col = 0
    row_count = 1
    child_column = 0
    single_child = True if len(graph.getRefsFromByNid(node)) == 1 else False

    for edge in graph.getRefsFromByNid(node):
        eid, n1, n2, eprops = edge
        computeGraphLayout(graph, n2)

        nid, nprops = graph.getNode(n2)

        if nprops['row_count'] + 1 > row_count:
            row_count = nprops['row_count'] + 1

        child_column = nprops['col']

    cur_node_edges = graph.getRefsFromByNid(node)
    cur_node, cur_props = graph.getNode(node)

    if layout is GraphLayoutType.Wide and len(cur_node_edges) == 2:
        left_edge = cur_node_edges[0]
        right_edge = cur_node_edges[1]

        # left and right n1 are the current node
        leid, ln1, ln2, leprops = left_edge
        reid, rn1, rn2, reprops = right_edge

        lid, lprops = graph.getNode(ln2)
        rid, rprops = graph.getNode(rn2)

        if len(graph.getRefsFromByNid(ln2)) == 0:
            lcol = rprops['col'] - 2
            lprops['col'] = lcol
            add = -lcol if lcol < 0 else 0
            adjustGraphLayout(graph, rn2, add, 1)
            adjustGraphLayout(graph, ln2, add, 1)
            col = rprops['col_count'] + add

        elif len(graph.getRefsFromByNid(rn2)) == 0:
            adjustGraphLayout(graph, ln2, 0, 1)
            adjustGraphLayout(graph, rn2, lprops['col'] + 2, 1)
            col = max(lprops['col_count'], rprops['col'] + 2)

        else:
            adjustGraphLayout(graph, ln2, 0, 1)
            adjustGraphLayout(graph, rn2, lprops['col_count'], 1)
            col = lprops['col_count'] + rprops['col_count']

        cur_props['col_count'] = max(2, col)
        if layout is GraphLayoutType.Medium:
            cur_props['col'] = (lprops['col'] + rprops['col']) // 2
        else:
            cur_props['col'] = child_column if single_child else (col - 2) // 2

    else:

        for edge in graph.getRefsFromByNid(node):
            eid, n1, n2, eprops = edge
            adjustGraphLayout(graph, n2, col, 1)

            nid, nprops = graph.getNode(n2)
            col += nprops['col_count']

        if col >= 2:
            cur_props['col'] = child_column if single_child else (col - 2) // 2
            cur_props['col_count'] = col
        else:
            cur_props['col'] = 0
            cur_props['col_count'] = 2

    cur_props['row'] = 0
    cur_props['row_count'] = row_count


def prepareMetaData(graph: codegraph.CodeBlockGraph):
    for node in graph.getNodes():
        nid, nprops = node
        nprops['col'] = 0
        nprops['col_count'] = 0
        nprops['row'] = 0
        nprops['row_count'] = 0


class ReflowLayout(vg_layout.GraphLayout):
    def __init__(self, graph: codegraph.CodeBlockGraph):

        super(ReflowLayout, self).__init__(graph)

        self.width_pad = 80
        self.height_pad = 80
        self.distance = 30

        # distance between edges of a node
        self.node_edge_distance = 10

        self._width = 0
        self._height = 0

        self.table_row_size = defaultdict(lambda: 0)
        self.table_col_size = defaultdict(lambda: 0)
        self.cell_row_pos = defaultdict(lambda: 0)
        self.cell_col_pos = defaultdict(lambda: 0)

        self._lines_in_x_gap = defaultdict(lambda: 0)
        self._lines_in_y_gap = defaultdict(lambda: 0)

        # keep track of how many node edges have been used
        # {nodeID: (inputCnt, outputCnt)}
        self._nodesEdgeTrack = dict()

    def getLayoutSize(self):
        """
        Return the width,height of this layout.
        """
        return self._width, self._height

    def _positionNodes(self):
        width = 0
        height = 0
        num_rows, num_cols = 0, 0

        self.table_row_size.clear()
        self.table_col_size.clear()
        self.cell_row_pos.clear()
        self.cell_col_pos.clear()

        # first collect all the row, col, size info for the nodes
        for node in self.graph.getNodes():
            nid, nprops = node
            xsize, ysize = nprops.get('size', zero_zero)

            row, col = nprops['row'], nprops['col']
            # print(row, col)
            self.table_col_size[col] = max(self.table_col_size[col], xsize)
            self.table_row_size[row] = max(self.table_row_size[row], ysize)

            num_rows = max(num_rows, row)
            num_cols = max(num_cols, col)

        # now calculate the collective size of the table
        for r in range(num_rows + 1):
            height += self.height_pad
            self.cell_row_pos[r] = height
            height += self.table_row_size[r]
        height += self.height_pad

        for c in range(num_cols + 1):
            width += self.width_pad
            self.cell_col_pos[c] = width
            width += self.table_col_size[c]
        width += self.width_pad

        # now place the nodes on their calculated positions
        for node in self.graph.getNodes():
            nid, nprops = node
            xsize, ysize = nprops.get('size', zero_zero)
            row, col = nprops['row'], nprops['col']

            col_sz, row_sz = self.table_col_size[col], self.table_row_size[row]
            cell_x, cell_y = self.cell_col_pos[col], self.cell_row_pos[row]

            nodex = cell_x + ((col_sz - xsize) // 2)
            nodey = cell_y + ((row_sz - ysize) // 2)
            # print(nodex, nodey)
            nprops['position'] = (nodex, nodey)

        self._width, self._height = width, height
        return width, height

    def layoutGraph(self):
        # must set 'position' -> (x, y) property to every node
        # can rely on 'cbva' -> int = code block virtual address, 'cbsize' ->  properties of the node
        # caller must have populated 'size' -> (w, h) property of the node

        rootnodes = self.graph.getHierRootNodes()
        rootnode = rootnodes[0]
        nid, nprops = rootnode

        prepareMetaData(self.graph)
        computeGraphLayout(self.graph, nid)
        self._positionNodes()

        # Finally, we calculate the drawing for the edge lines
        self._calcEdgeLines()

    def _getNextInGap(self, x: int = 0, y: int = 0):
        if x != 0:
            lines_in_gap = self._lines_in_x_gap
        if y != 0:
            lines_in_gap = self._lines_in_y_gap

        cline = lines_in_gap.get(x)
        cline += 1
        lines_in_gap[x] = cline
        return cline

    def _calcNodeEdgeStartPos(self, nid: int):
        nprops = self.graph.getNodeProps(nid)
        nwidth, nheight = nprops.get('size')
        xpos, ypos = nprops.get('position')

        node_input_edges = self.graph.getRefsToByNid(nid)
        node_output_edges = self.graph.getRefsFromByNid(nid)

        def _start_x_pos(edges: list) -> tuple:
            try:
                distance = nwidth // len(edges)
                distance = min(self.node_edge_distance, distance)
                edge_start_x_pos = (nwidth // 2) - ((len(edges) // 2) * distance)
            except ZeroDivisionError:
                return 0, 0

            return distance, edge_start_x_pos

        i_d, start_x_pos_input = _start_x_pos(node_input_edges)
        start_x_pos_input += xpos
        o_d, start_x_pos_output = _start_x_pos(node_output_edges)
        start_x_pos_output += xpos

        nprops['input_edge_distance'] = i_d
        nprops['input_edge_start_pos'] = (start_x_pos_input, ypos)
        nprops['output_edge_distance'] = o_d
        nprops['output_edge_start_pos'] = (start_x_pos_output, ypos + nheight)

    def getEdgePoints(self, edge: tuple) -> tuple:
        """
        Get a set of possible points for the given edge.
        :param edge: (eid, node1, node2, eprops)
        :return: in pixels (src_x, src_y), (dst_x, dst_y)
        """

        eid, nsrc, ndst, einfo = edge

        src_output_edges = self.graph.getRefsFromByNid(nsrc)
        nsrc_props = self.graph.getNodeProps(nsrc)
        if nsrc_props.get('output_edge_start_pos') is None:
            self._calcNodeEdgeStartPos(nsrc)

        dst_input_edges = self.graph.getRefsToByNid(ndst)
        ndst_props = self.graph.getNodeProps(ndst)
        if ndst_props.get('input_edge_start_pos') is None:
            self._calcNodeEdgeStartPos(ndst)

        sidx = src_output_edges.index(edge)
        src_x, src_y = nsrc_props['output_edge_start_pos']
        s_d = nsrc_props['output_edge_distance']
        src_x += sidx * s_d

        didx = dst_input_edges.index(edge)
        dst_x, dst_y = ndst_props['input_edge_start_pos']
        d_d = ndst_props['input_edge_distance']
        dst_x += didx * d_d

        return (src_x, src_y), (dst_x, dst_y)

    def _calcEdgeLines(self):
        self._lines_in_x_gap.clear()
        self._lines_in_y_gap.clear()

        h_hpad = self.width_pad / 2
        h_vpad = self.height_pad / 2

        for edge in self.graph.getEdges():
            eid, n1, n2, einfo = edge

            pre_lines = []
            post_lines = []

            # src
            pinfo = self.graph.getNodeProps(n1)
            pw, ph = pinfo.get('size', (0, 0))
            pcbva = pinfo.get('cbva')
            prow = pinfo.get('row')
            pcol = pinfo.get('col')
            px, py = pinfo.get('position')

            # dst
            kinfo = self.graph.getNodeProps(n2)
            kw, kh = kinfo.get('size')
            kcbva = pinfo.get('cbva')
            krow = kinfo.get('row')
            kcol = kinfo.get('col')
            kx, ky = kinfo.get('position')

            (x1, y1), (x2, y2) = self.getEdgePoints(edge)

            if prow == krow:
                b = [(x1, y1),
                     (x1, y1 - h_vpad),
                     (x2, y2 - h_vpad),
                     (x2, y2),
                     ]

            elif prow < krow:
                pre_lines = [(x1, y1), (x1, y1)]
                post_lines = [(x2, y2), (x2, y2)]

                b = [(x1, y1),
                     (x1, y1 + h_vpad),
                     (x2, y2 - h_vpad),
                     (x2, y2),
                     ]

            else:
                pre_lines = [(x1, y1), (x1, y1)]

                b = [(x1, y1),
                     (x1, y1 + h_vpad),
                     (x2, y2 - h_vpad),
                     (x2, y2),
                     ]

            einfo['edge_points'] = pre_lines + b + post_lines


class _ReflowLayout(vg_layout.GraphLayout):
    def __init__(self, graph: codegraph.CodeBlockGraph):

        super(ReflowLayout, self).__init__(graph)

        self._sorted_nodes = list()
        self.width_pad = 20
        self.height_pad = 40
        self.distance = 50

    def getLayoutSize(self):
        """
        Return the width,height of this layout.
        """
        height = 0
        width = 0
        for layer in self.layers:

            lheight = 0
            lwidth = 0

            for nid, ninfo in layer:
                xsize, ysize = ninfo.get('size', zero_zero)
                lheight = max(lheight, ysize + self.height_pad)
                lwidth += xsize + self.width_pad

            height += lheight
            width = max(lwidth, width)

        return width, height

    def layoutGraph(self):
        # must set 'position' -> (x, y) property to every node
        # can rely on 'cbva' -> int = code block virtual address, 'cbsize' ->  properties of the node
        # caller must have populated 'size' -> (w, h) property of the node

        self._sorted_nodes = self.graph.getNodes()
        self._sorted_nodes.sort(key=lambda n: n[1].get('cbva'), reverse=True)

        x = self.distance
        y = 0
        for nid, nprop in self._sorted_nodes:
            y += self.distance
            w, h = nprop['size']
            nprop['position'] = (x, y)
            y += h

        # Finally, we calculate the drawing for the edge lines
        self._calcEdgeLines()

    def _calcEdgeLines(self):
        h_hpad = self.width_pad / 2
        h_vpad = self.height_pad / 2
        voffset = 0
        kvoffset = 0

        for eid, n1, n2, einfo in self.graph.getEdges():

            pre_lines = []
            post_lines = []

            pinfo = self.graph.getNodeProps(n1)
            pw, ph = pinfo.get('size', (0, 0))
            pcbva = pinfo.get('cbva')

            kinfo = self.graph.getNodeProps(n2)
            kw, kh = kinfo.get('size')
            kcbva = pinfo.get('cbva')

            if pcbva == kcbva:
                x1, y1 = vg_layout.exit_pos(pinfo)
                x2, y2 = vg_layout.entry_pos(kinfo)

                xhalf = (x1 - x2) / 2

                b = [(x1, y1),
                     (x1, y1 - h_vpad),
                     (x2, y2 - h_vpad),
                     (x2, y2),
                     ]

            elif pcbva < kcbva:

                x1, y1 = vg_layout.entry_pos(pinfo)
                x2, y2 = vg_layout.exit_pos(kinfo)

                kwidth, kheight = kinfo.get('size', (0, 0))

                pre_lines = [(x1, y1), (x1, y1 + voffset)]
                post_lines = [(x2, y2), (x2, y2 + kvoffset)]

                b = [(x1, y1 + voffset),
                     (x1, y1 + voffset + h_vpad),
                     (x2, y2 + kvoffset + h_vpad),
                     (x2, y2 + kvoffset),
                     ]

            else:

                x1, y1 = vg_layout.exit_pos(pinfo)
                x2, y2 = vg_layout.entry_pos(kinfo)

                pre_lines = [(x1, y1), (x1, y1 + voffset)]

                b = [(x1, y1 + voffset),
                     (x1, y1 + voffset + h_vpad),
                     (x2, y2 - h_vpad),
                     (x2, y2),
                     ]

            # bez_lines = vg_bezier.calculate_bezier(b, 20)

            einfo['edge_points'] = pre_lines + b + post_lines
