"""
A package for each of the different layout managers.
"""

from vivisect import codegraph


# Some helper utils...
def exit_pos(ninfo):
    """Return the EXIT point for a given node in the graph"""
    x, y = ninfo.get('position')
    xsize, ysize = ninfo.get('size', (0, 0))
    return (x + xsize / 2, y + ysize)


def entry_pos(ninfo):
    """Return the ENTRY point for a given node in the graph"""
    x, y = ninfo.get('position')
    xsize, ysize = ninfo.get('size', (0, 0))
    return (x + xsize / 2, y)


def center_pos(ninfo):
    """Return the CENTER point for a given node in the graph"""
    x, y = ninfo.get('position')
    xsize, ysize = ninfo.get('size', (0, 0))
    return (x + (xsize / 2), y + (ysize / 2))


class GraphLayout:
    """
    A graph layout uses several graph meta properties and node properties
    to communicate with a renderer which is expected to display the graph:

    size = ( width, height )    - Set by the renderer
    position = ( x, y )         - Set by the layout
    repr = <display text>       - A fallback for what to display on a node
    """

    def __init__(self, graph: codegraph.CodeBlockGraph):
        self.graph = graph

    def layoutGraph(self):
        """
        Layout the graph nodes and edges
        """
        raise NotImplementedError('%s must implement layoutGraph()!' % self.__class__.__name__)

    def getLayoutSize(self):
        raise NotImplementedError('%s must implement getLayoutSize()!' % self.__class__.__name__)

    def renderGraph(self, rend):
        """
        Render the graph to the given renderer.
        """
        rend.setNodeSizes(self.graph)
        self.layoutGraph()
        width, height = self.getLayoutSize()
        self.graph.setMeta('size', (width, height))

        rend.renderGraph()
