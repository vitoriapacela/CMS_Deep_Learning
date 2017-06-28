colors_contrasting1 = \
[
(0.875, 0.122, 0.122), # Red
(0.875, 0.522, 0.122), # Orange
(0.400, 0.400, 0.400), # Gray
(0.082, 0.812, 0.255), # Green
(0.067, 0.639, 0.831), # Turquoise
(0.424, 0.322, 0.933), # Purple
(0.871, 0.024, 0.588), # Pink
(0.820, 0.808, 0.075), # Yellow


(0.557, 0.039, 0.039), # Red
(0.518, 0.333, 0.078), # Orange
(0.098, 0.098, 0.098), # Black
(0.027, 0.471, 0.129), # Green
(0.020, 0.361, 0.475), # Turquoise
(0.196, 0.122, 0.576), # Purple
(0.490, 0.004, 0.329), # Pink
(0.459, 0.455, 0.035), # Yellow


(0.965, 0.533, 0.533), # Red
(0.965, 0.757, 0.533), # Orange
(0.800, 0.800, 0.800), # Light Gray
(0.620, 0.976, 0.702), # Green
(0.522, 0.863, 0.976), # Turquoise
(0.639, 0.584, 0.910), # Purple
(0.992, 0.506, 0.827), # Pink
(0.976, 0.969, 0.522), # Yellow

]

def resolveColors(colors):
    if isinstance(colors,str):
        if colors in locals():
            colors = locals()[colors]
        elif colors in globals():
            colors = globals()[colors]
    return colors
        


#A list of colors that contrast <- well sort of there is probably a better list
colors_contrasting2 =[(0, 0, 1.0),
(0, 1.0, 0),
(1.0, 0, 0),
(0, 1.0, 1.0),
(1.0, 0, 1.0),
(1.0, 1.0, 0),
(1.0, 1.0, 1.0),
(0, 0, 0.5),
(0, 0.5, 0),
(0.5, 0, 0),
(0, 0.5, 0.5),
(0.5, 0, 0.5),
(0.5, 0.5, 0),
(0.5, 0.5, 0.5)
]
#A list of lower saturation colors that contrast <- well sort of there is probably a better list
colors_contrasting3 = \
[
#Shade 0
(0.675,0.412,0.231),
(0.224,0.204,0.471),
(0.494,0.631,0.216),
(0.145,0.427,0.38),
(0.675,0.573,0.231),
(0.553,0.188,0.38),


#Shade 1
(1,0.745,0.573),
(0.518,0.502,0.753),
(0.816,0.949,0.541),
(0.424,0.757,0.702),
(1,0.91,0.608),
(0.863,0.49,0.686),

#Shade 3
(0.631,0.255,0),
(0.125,0.09,0.584),
(0.392,0.592,0),
(0,0.875,0.725),
(0.843,0.647,0.012),
(0.49,0,0.259),

#Shade 2
(0.988,0.408,0.012),
(0.286,0.255,0.682),
(0.62,0.922,0.012),
(0.173,0.663,0.58),
(0.98,0.812,0.267),
(0.867,0,0.459),


#Shade 4
(0.404,0.212,0.078),
(0.078,0.059,0.361),
(0.278,0.376,0.075),
(0.012,0.325,0.271),
(0.518,0.4,0.012),
(0.322,0.094,0.216)
]




    
    


    
 



