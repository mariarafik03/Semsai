import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:SemsAi/business_logic/home/home_cubit.dart';
import 'package:SemsAi/business_logic/home/home_state.dart';
import 'package:SemsAi/core/colors.dart';
import 'package:SemsAi/presentation/screens/home/widgets/BromoBanners.dart';
import 'package:SemsAi/presentation/screens/home/widgets/CategoryChips.dart';
import 'package:SemsAi/presentation/screens/home/widgets/FeaturedList.dart';
import 'package:SemsAi/presentation/screens/home/widgets/topBar.dart';
import 'package:SemsAi/presentation/screens/chat/agent_chat_screen.dart';
import 'package:SemsAi/presentation/screens/favorite/favourite_screen.dart';
import 'package:SemsAi/presentation/screens/map/map_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<HomeCubit, HomeState>(
      builder: (context, state) {
        return Scaffold(
          backgroundColor: Colors.white,
          body: _buildBody(context, state),
          bottomNavigationBar: BottomNavigationBar(
            backgroundColor: Colors.white,
            selectedItemColor: myColors.orangeColor,
            unselectedItemColor: myColors.textGreyDark,
            showSelectedLabels: true,
            showUnselectedLabels: true,
            currentIndex: state.bottomNavIndex,
            onTap: (value) {
              context.read<HomeCubit>().changeBottomNavIndex(value);
            },
            type: BottomNavigationBarType.fixed,
            elevation: 10,
            items: const [
              BottomNavigationBarItem(icon: Icon(Icons.home), label: 'Home'),
              BottomNavigationBarItem(
                icon: Icon(Icons.favorite_border),
                label: 'Favorites',
              ),
              BottomNavigationBarItem(icon: Icon(Icons.map), label: 'Map'),
              BottomNavigationBarItem(
                icon: Icon(Icons.chat_bubble_rounded),
                label: 'AI Assistant',
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildWelcomeText() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        RichText(
          text: TextSpan(
            style: TextStyle(
              color: myColors.textGreyDark,
              fontSize: 26,
              fontWeight: FontWeight.w500,
            ),
            children: [
              const TextSpan(text: 'Hey, '),
              TextSpan(
                text: 'Welcome!',
                style: TextStyle(
                  color: myColors.welcomeBlue,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Text(
          "Let's start exploring",
          style: TextStyle(color: myColors.textGreyDark, fontSize: 16),
        ),
      ],
    );
  }

  Widget _buildSearchBar(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
      width: MediaQuery.of(context).size.width * 0.9,
      height: MediaQuery.of(context).size.height * 0.1,
      decoration: BoxDecoration(
        color: myColors.lightgrayColor,
        borderRadius: BorderRadius.circular(15),
      ),
      child: TextField(
        decoration: InputDecoration(
          icon: const Icon(Icons.search, color: Colors.black),
          hintText: 'Search House, villa. etc',
          hintStyle: TextStyle(color: myColors.textGreyDark),
          border: InputBorder.none,
        ),
      ),
    );
  }

  Widget _buildFeaturedHeader() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          'Featured Estates',
          style: TextStyle(
            color: myColors.textGreyDark,
            fontSize: 20,
            fontWeight: FontWeight.bold,
          ),
        ),
        TextButton(
          onPressed: () {},
          child: Text(
            'view all',
            style: TextStyle(
              color: myColors.orangeColor,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildBody(BuildContext context, HomeState state) {
    switch (state.bottomNavIndex) {
      case 0:
        return SafeArea(
          child: SingleChildScrollView(
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: 20.0,
                vertical: 12.0,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Topbar(),
                  const SizedBox(height: 30),
                  _buildWelcomeText(),
                  const SizedBox(height: 20),
                  _buildSearchBar(context),
                  const SizedBox(height: 20),
                  Categorychips(
                    onCategorySelected: (category) {
                      context.read<HomeCubit>().changeCategory(category);
                    },
                  ),
                  const SizedBox(height: 10),
                  const Bromobanners(),
                  const SizedBox(height: 15),
                  _buildFeaturedHeader(),
                  const SizedBox(height: 10),
                  Featuredlist(selectedCategory: state.selectedCategory),
                ],
              ),
            ),
          ),
        );
      case 1:
        return const FavouriteScreen();
      case 2:
        return const MapScreen();
      case 3:
        return const AgentChatScreen();
      default:
        return const Center(child: Text('Error'));
    }
  }
}
